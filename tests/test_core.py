import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from datetime import date
from hearthwood.config import ROOT
from hearthwood.triage import classify_rules,validate_input,validate_model_output,draft_issues
from hearthwood.providers import classify_openai,ProviderError
from hearthwood.reporting import build_report,report_markdown
from hearthwood import storage


def complaint(message='The desk arrived broken.'):
    return {'message':message,'customer':'Test Customer','product':'Linden desk','courier':'ParcelPath','order_id':'HW-12345'}


class TriageTests(unittest.TestCase):
    def test_refund_is_not_delivery(self):
        for text in ['Where is my money back?', 'My refund has not hit my account. I am still waiting.',
                     'The sofa is not damaged. My refund is overdue.']:
            self.assertEqual(classify_rules(complaint(text))['category'],'refund_delay')

    def test_negated_damage_with_missing_parts(self):
        result=classify_rules(complaint("There are screws missing, but the table isn't broken."))
        self.assertEqual(result['category'],'missing_parts')
        self.assertNotIn('damaged_item',result['secondary'])

    def test_safety_is_urgent(self):
        for text in ['The wardrobe fell onto my child and they are hurt.',
                     "Smoke is coming from the bed's USB socket.", 'The chair collapsed and I was injured.']:
            result=classify_rules(complaint(text))
            self.assertEqual((result['category'],result['urgency'],result['team']),('product_safety','urgent','Product Safety'))

    def test_explicit_safety_denial_is_not_positive_evidence(self):
        result=classify_rules(complaint('No smoke or injury. The instructions are missing.'))
        self.assertFalse(result['safety_flag'])

    def test_vague_is_not_low(self):
        result=classify_rules(complaint('This is unacceptable.'))
        self.assertTrue(result['uncertain'])
        self.assertEqual(result['urgency'],'normal')

    def test_drafts_do_not_claim_dispatch(self):
        for text in ['There are missing screws.','My refund is overdue.','Wrong item delivered.']:
            result=classify_rules(complaint(text))
            self.assertFalse(draft_issues(result['draft']))
            self.assertTrue(result['human_review_required'])
        self.assertTrue(draft_issues("We're sending the missing parts out to you now."))

    def test_input_validation(self):
        for obj in [None,[],{'message':7},{'message':''},{'message':'x'*8001}]:
            with self.assertRaises(ValueError):validate_input(obj)

    def test_schema_and_evidence_validation(self):
        base=classify_rules(complaint())
        keys=['category','secondary','urgency','sentiment','summary','evidence','uncertain','reason','safety_flag']
        data={k:base[k] for k in keys}
        validate_model_output(data,complaint()['message'])
        with self.assertRaises(ValueError):validate_model_output({**data,'evidence':['An invented sentence']},complaint()['message'])
        with self.assertRaises(ValueError):validate_model_output({**data,'category':'not_real'},complaint()['message'])

    def test_openai_contract_and_safety_override(self):
        message='The wardrobe fell onto my child and they are hurt.'
        data={'category':'unclear','secondary':[],'urgency':'low','sentiment':'neutral','summary':'Customer reports a problem.','evidence':[message],'uncertain':True,'reason':'Needs review.','safety_flag':False}
        response=Mock();response.read.return_value=json.dumps({'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(data)}]}]}).encode()
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        with patch('urllib.request.urlopen',return_value=response) as send:
            result=classify_openai(complaint(message),'test-key','test-model')
            payload=json.loads(send.call_args.args[0].data)
            self.assertFalse(payload['store'])
            self.assertTrue(payload['text']['format']['strict'])
            self.assertNotIn('true_category',payload['input'])
            self.assertEqual(result['engine'],'OpenAI')
            self.assertEqual(result['urgency'],'urgent')

    def test_missing_key_and_bad_response_are_explicit(self):
        with self.assertRaises(ProviderError):classify_openai(complaint(),'')
        response=Mock();response.read.return_value=b'{"status":"incomplete"}'
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        with patch('urllib.request.urlopen',return_value=response):
            with self.assertRaises(ProviderError):classify_openai(complaint(),'test-key')


class ReportTests(unittest.TestCase):
    def case(self,category,day='2026-11-09',product='Linden desk',courier='ParcelPath',id='T1'):
        return {'id':id,'created_at':day+'T12:00:00+00:00','complaint':{'date':day,'product':product,'courier':courier},'result':{'category':category,'urgency':'normal','safety_flag':False}}

    def test_empty_and_single_category_reports(self):
        for cases in [[],[self.case('assembly_help')],[self.case('missing_parts')]]:
            report=build_report(cases,'2026-11-09')
            self.assertEqual(report['total'],len(cases))
            self.assertTrue(report_markdown(report))

    def test_window_filters_old_and_future_records(self):
        cases=[self.case('damaged_item',d,id=d) for d in ['2026-10-12','2026-10-13','2026-11-09','2026-11-10']]
        report=build_report(cases,'2026-11-09')
        self.assertEqual(report['total'],2)
        self.assertEqual(report['excluded'],2)

    def test_signal_has_refs_and_qualification(self):
        report=build_report([self.case('damaged_item',id=str(i)) for i in range(4)],'2026-11-09')
        self.assertEqual(len(report['insights'][0]['evidence_ids']),4)
        self.assertIn('not proof',report['insights'][0]['hypothesis'])


class StorageTests(unittest.TestCase):
    def setUp(self):
        testroot=(ROOT/'runtime/tests').resolve();testroot.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=testroot)
        assert Path(self.temp.name).resolve().parent==testroot
        self.old=os.environ.get('HEARTHWOOD_DB');os.environ['HEARTHWOOD_DB']=str(Path(self.temp.name)/'test.sqlite3')
        storage.init()

    def tearDown(self):
        if self.old is None:os.environ.pop('HEARTHWOOD_DB',None)
        else:os.environ['HEARTHWOOD_DB']=self.old
        self.temp.cleanup()

    def new(self,message='The desk arrived broken.'):
        c=complaint(message);return storage.create_case(c,classify_rules(c))

    def changes(self,row,**kwargs):
        r=row['result'];return {'category':r['category'],'urgency':r['urgency'],'draft':r['draft'],
            'reviewer':'Test reviewer','note':'Checked against the complaint.','decision':'approve','acknowledged':True,'version':row['version'],**kwargs}

    def test_review_is_durable_and_repeated_approval_blocked(self):
        row=self.new();updated=storage.review(row['id'],self.changes(row))
        self.assertEqual(updated['status'],'approved')
        with self.assertRaises(ValueError):storage.review(row['id'],self.changes(row))
        self.assertEqual(len(storage.events()),2)

    def test_safety_cannot_be_downgraded(self):
        row=self.new('The wardrobe fell onto my child and they are hurt.')
        with self.assertRaisesRegex(ValueError,'must stay urgent'):
            storage.review(row['id'],self.changes(row,category='unclear',urgency='low'))

    def test_uncertainty_and_edits_require_note(self):
        row=self.new('This is unacceptable.')
        with self.assertRaisesRegex(ValueError,'review note'):storage.review(row['id'],self.changes(row,note=''))

    def test_approval_requires_acknowledgement_and_safe_draft(self):
        row=self.new()
        with self.assertRaises(ValueError):storage.review(row['id'],self.changes(row,acknowledged=False))
        with self.assertRaisesRegex(ValueError,'cannot verify'):
            storage.review(row['id'],self.changes(row,draft="We've issued your refund."))

    def test_stale_review_version_rejected(self):
        row=self.new();storage.review(row['id'],self.changes(row,decision='save'))
        with self.assertRaisesRegex(ValueError,'another window'):storage.review(row['id'],self.changes(row))

    def test_rejected_draft_is_not_approved(self):
        row=self.new();storage.review(row['id'],self.changes(row,decision='reject'))
        self.assertEqual(storage.get_case(row['id'])['status'],'rejected')

    def test_seed_is_repeatable_and_ground_truth_not_exposed(self):
        storage.seed_history();storage.seed_history()
        self.assertEqual(len(storage.cases()),75)
        self.assertNotIn('true_category',storage.cases()[0]['complaint'])


if __name__=='__main__':unittest.main()
