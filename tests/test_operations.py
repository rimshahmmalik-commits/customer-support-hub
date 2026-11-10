import base64
import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, Mock
from hearthwood import storage, images, messaging
from hearthwood.config import ROOT
from hearthwood.dashboard import build_dashboard
from hearthwood.triage import classify_rules, validate_input
from hearthwood.providers import extract_image, ProviderError

PNG='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII='
ENV={'SMTP_HOST':'smtp.example.com','SMTP_PORT':'587','SMTP_USER':'sender@example.com',
     'SMTP_PASSWORD':'TEST_SMTP_SECRET','SMTP_FROM':'sender@example.com',
     'TEAM_EMAIL_REFUND_DELAY':'finance@example.com'}


class OperationsTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'runtime/tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.env=patch.dict(os.environ,{'HEARTHWOOD_DB':str(Path(self.temp.name)/'test.sqlite3')})
        self.env.start();storage.init();images.init();messaging.init()

    def tearDown(self):
        self.env.stop();self.temp.cleanup()

    def case(self, message='My refund has not reached my account.'):
        complaint=validate_input({'customer':'Test Customer','customer_email':'customer@example.com',
                                 'message':message,'order_id':'HW-TEST'})
        return storage.create_case(complaint,classify_rules(complaint))

    def approve(self,row):
        r=row['result']
        return storage.review(row['id'],{'version':row['version'],'category':r['category'],
            'urgency':r['urgency'],'draft':r['draft'],'reviewer':'Test reviewer','note':'Checked source.',
            'decision':'approve','acknowledged':True})

    def test_empty_dashboard_has_no_fabricated_metrics(self):
        result=build_dashboard([])
        self.assertEqual((result['total'],result['pending'],result['approved']),(0,0,0))
        self.assertEqual(sum(x['count'] for x in result['daily']),0)
        self.assertEqual(result['brief'],[])

    def test_dashboard_counts_age_and_does_not_call_approval_resolution(self):
        row=self.case()
        with storage.db() as con:
            con.execute("UPDATE cases SET created_at='2026-11-08T08:00:00+00:00' WHERE id=?",(row['id'],))
        result=build_dashboard(storage.cases(),now=datetime(2026,11,10,8,tzinfo=timezone.utc))
        self.assertEqual(result['aged_pending'],1)
        self.assertEqual(result['attention'][0]['age_hours'],48)
        self.approve(storage.get_case(row['id']))
        result=build_dashboard(storage.cases())
        self.assertEqual((result['pending'],result['approved']),(0,1))
        self.assertNotIn('resolved',result)

    def test_training_dashboard_has_no_fake_pending_reviews(self):
        storage.seed_history();result=build_dashboard(storage.cases('sample'),'sample')
        self.assertEqual((result['total'],result['pending']),(75,0))
        self.assertEqual(result['attention'],[])

    def test_dashboard_prioritises_urgent_over_newer_normal(self):
        urgent=self.case('The wardrobe collapsed and I was injured.')
        self.case()
        result=build_dashboard(storage.cases())
        self.assertEqual(result['attention'][0]['id'],urgent['id'])
        self.assertEqual(result['urgent_pending'],1)

    def test_image_upload_and_binding_preserve_evidence(self):
        uploaded=images.upload(PNG,'complaint.png');raw=images.get(uploaded['id'])
        self.assertEqual(raw['mime'],'image/png')
        self.assertEqual(len(raw['sha256']),64)
        c=validate_input({'message':'The sofa arrived broken.'})
        case=storage.create_case(c,classify_rules(c),uploaded['id'])
        self.assertEqual(images.for_case(case['id'])[0]['id'],uploaded['id'])
        with self.assertRaises(ValueError):storage.create_case(c,classify_rules(c),uploaded['id'])

    def test_image_rejects_svg_and_false_mime(self):
        for data in ['data:image/svg+xml;base64,PHN2Zz4=',
                     'data:image/png;base64,'+base64.b64encode(b'x'*50).decode()]:
            with self.assertRaises(ValueError):images.upload(data,'bad.png')

    def test_image_extraction_is_explicit_and_transcript_stays_reviewable(self):
        with self.assertRaises(ProviderError):extract_image(PNG,'')
        reply={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps({'text':'Refund overdue','notes':'Check the order reference manually.'})}]}]}
        response=Mock();response.read.return_value=json.dumps(reply).encode()
        context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False)
        with patch('hearthwood.providers.urllib.request.urlopen',return_value=context) as request:
            result=extract_image(PNG,'test-key')
        self.assertTrue(result['review_required'])
        sent=json.loads(request.call_args.args[0].data)
        self.assertEqual(sent['input'][0]['content'][1]['type'],'input_image')
        self.assertFalse(sent['store'])

    def test_email_validation_blocks_header_injection(self):
        self.assertFalse(messaging.valid_email('a@example.com\nBcc: other@example.com'))
        with self.assertRaises(ValueError):validate_input({'message':'Refund please','customer_email':'invalid'})

    def test_customer_email_needs_approval_and_preview_is_stable(self):
        row=self.case()
        with self.assertRaisesRegex(ValueError,'Approve'):messaging.preview(row['id'],'customer')
        row=self.approve(row)
        first=messaging.preview(row['id'],'customer');second=messaging.preview(row['id'],'customer')
        self.assertEqual(first['id'],second['id'])
        self.assertEqual(first['body'],row['result']['draft'])
        self.assertEqual(first['recipient'],'customer@example.com')

    def test_department_uses_configured_route_and_keeps_source(self):
        row=self.case()
        with patch.dict(os.environ,ENV):preview=messaging.preview(row['id'],'department')
        self.assertEqual(preview['recipient'],'finance@example.com')
        self.assertIn(row['complaint']['message'],preview['body'])
        self.assertIn('not attached',preview['body'])

    def test_missing_mailbox_never_sends(self):
        row=self.approve(self.case());m=messaging.preview(row['id'],'customer')
        with patch.dict(os.environ,{'SMTP_HOST':''}),patch('hearthwood.messaging.smtplib.SMTP') as smtp:
            with self.assertRaisesRegex(ValueError,'not connected'):messaging.submit(m['id'],'Tester',True)
            smtp.assert_not_called()

    def test_smtp_submission_requires_ack_and_blocks_duplicate_attempt(self):
        row=self.approve(self.case());m=messaging.preview(row['id'],'customer')
        smtp=Mock();smtp.__enter__=Mock(return_value=smtp);smtp.__exit__=Mock(return_value=False);smtp.send_message.return_value={}
        with patch.dict(os.environ,ENV),patch('hearthwood.messaging.smtplib.SMTP',return_value=smtp):
            with self.assertRaises(ValueError):messaging.submit(m['id'],'Tester',False)
            result=messaging.submit(m['id'],'Tester',True)
            self.assertEqual(result['state'],'submitted')
            smtp.starttls.assert_called_once();smtp.send_message.assert_called_once()
            with self.assertRaisesRegex(ValueError,'already attempted'):messaging.submit(m['id'],'Tester',True)
        self.assertNotIn('TEST_SMTP_SECRET',json.dumps(storage.events()))

    def test_uncertain_smtp_outcome_is_not_retried(self):
        row=self.approve(self.case());m=messaging.preview(row['id'],'customer')
        with patch.dict(os.environ,ENV),patch('hearthwood.messaging.smtplib.SMTP',side_effect=TimeoutError):
            with self.assertRaisesRegex(ValueError,'could not be confirmed'):messaging.submit(m['id'],'Tester',True)
            with self.assertRaisesRegex(ValueError,'already attempted'):messaging.submit(m['id'],'Tester',True)
        self.assertEqual(messaging.case_messages(row['id'])[0]['state'],'unknown')

    def test_department_preview_goes_stale_after_review_edit(self):
        row=self.case()
        with patch.dict(os.environ,ENV):m=messaging.preview(row['id'],'department')
        self.approve(row)
        with patch.dict(os.environ,ENV),patch('hearthwood.messaging.smtplib.SMTP') as smtp:
            with self.assertRaisesRegex(ValueError,'case changed'):messaging.submit(m['id'],'Tester',True)
            smtp.assert_not_called()


if __name__=='__main__':unittest.main()
