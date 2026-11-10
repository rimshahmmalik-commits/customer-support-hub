import json
from pathlib import Path
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from hearthwood import storage,images,messaging
from hearthwood.config import ROOT
from hearthwood.providers import ProviderError
from app import Handler,export_csv,MAX_BODY


class HttpTests(unittest.TestCase):
    def setUp(self):
        root=(ROOT/'runtime/tests').resolve();root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root)
        assert Path(self.temp.name).resolve().parent==root
        self.old=os.environ.get('HEARTHWOOD_DB');os.environ['HEARTHWOOD_DB']=str(Path(self.temp.name)/'http.sqlite3')
        storage.init();images.init();messaging.init();self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        if self.old is None:os.environ.pop('HEARTHWOOD_DB',None)
        else:os.environ['HEARTHWOOD_DB']=self.old
        self.temp.cleanup()

    def request(self,path,body=None,raw=None,headers=None):
        request=urllib.request.Request(self.base+path,
            data=raw if raw is not None else json.dumps(body).encode() if body is not None else None,
            headers=headers or ({'Content-Type':'application/json'} if body is not None or raw is not None else {}))
        try:
            with urllib.request.urlopen(request,timeout=3) as response:return response.status,response.read()
        except urllib.error.HTTPError as e:return e.code,e.read()

    def payload(self):
        return {'complaint':{'customer':'Test','product':'Malmo wardrobe','message':'Where is my money back?'},'engine':'rules'}

    def test_static_and_private_file_boundaries(self):
        self.assertEqual(self.request('/')[0],200)
        self.assertEqual(self.request('/app.js')[0],200)
        for path in ['/.env','/runtime/hearthwood.sqlite3','/../app.py','/app.py']:
            self.assertEqual(self.request(path)[0],404)

    def test_malformed_and_oversize_inputs(self):
        self.assertEqual(self.request('/api/triage',raw=b'{oops')[0],400)
        self.assertEqual(self.request('/api/triage',raw=b'x'*(MAX_BODY+1))[0],413)
        self.assertEqual(self.request('/api/triage',body=[])[0],400)
        self.assertEqual(self.request('/api/triage',body={'complaint':{'message':3}})[0],400)

    def test_cross_origin_and_wrong_content_type_blocked(self):
        self.assertEqual(self.request('/api/triage',body=self.payload(),headers={'Content-Type':'application/json','Origin':'https://example.com'})[0],403)
        self.assertEqual(self.request('/api/triage',raw=b'{}',headers={'Content-Type':'text/plain'})[0],415)

    def test_config_never_discloses_api_key(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'TEST_SECRET_DO_NOT_LEAK'}):
            status,body=self.request('/api/config')
            self.assertEqual(status,200);self.assertNotIn(b'TEST_SECRET',body)

    def test_failed_api_has_no_hidden_fallback(self):
        body={**self.payload(),'engine':'openai','api_key':'FAKE_SECRET_FOR_TEST'}
        with patch('app.classify_openai',side_effect=ProviderError('Simulated provider failure')):
            self.assertEqual(self.request('/api/triage',body=body)[0],502)
            self.assertEqual(storage.cases(),[])
            code,result=self.request('/api/triage',body={**body,'allow_fallback':True})
        row=json.loads(result)
        self.assertEqual(code,201);self.assertEqual(row['result']['engine'],'Keyword rules')
        self.assertTrue(row['result']['fallback_reason'])
        self.assertNotIn('FAKE_SECRET',json.dumps(storage.events())+json.dumps(storage.cases()))

    def test_post_persists_and_export_is_valid(self):
        status,body=self.request('/api/triage',body=self.payload())
        self.assertEqual(status,201)
        case=json.loads(body);self.assertEqual(case['status'],'pending')
        self.assertEqual(case['result']['category'],'refund_delay')
        self.assertIn(case['id'].encode(),self.request('/api/export.csv')[1])

    def test_csv_formula_values_are_escaped(self):
        case={'id':'T1','complaint':{'customer':'=SUM(1,2)'},'result':{'category':'unclear','urgency':'normal','team':'General Support','engine':'Keyword rules','draft':'Draft'},'status':'pending','reviewer':None,'review_note':None,'reviewed_at':None}
        self.assertIn("'=SUM",export_csv([case]))

    def test_empty_report_endpoint(self):
        code,body=self.request('/api/report?source=interactive')
        self.assertEqual(code,200);self.assertEqual(json.loads(body)['total'],0)

    def test_dashboard_uses_requested_dataset(self):
        code,body=self.request('/api/dashboard?source=interactive')
        self.assertEqual(code,200);self.assertEqual(json.loads(body)['pending'],0)
        self.assertEqual(self.request('/api/dashboard?source=invalid')[0],400)

    def test_image_transcript_requires_human_confirmation(self):
        from test_operations import PNG
        code,body=self.request('/api/images',body={'name':'complaint.png','data':PNG})
        self.assertEqual(code,201);image_id=json.loads(body)['id']
        self.assertEqual(self.request('/api/attachments/'+image_id)[0],200)
        images.save_extraction(image_id,'My refund is overdue.')
        body={**self.payload(),'image_id':image_id}
        self.assertEqual(self.request('/api/triage',body=body)[0],400)
        code,result=self.request('/api/triage',body={**body,'image_text_reviewed':True})
        self.assertEqual(code,201)
        case_id=json.loads(result)['id']
        self.assertEqual(len(json.loads(self.request('/api/case-evidence/'+case_id)[1])),1)

    def test_email_api_never_sends_unapproved_customer_reply(self):
        code,result=self.request('/api/triage',body=self.payload());case_id=json.loads(result)['id']
        self.assertEqual(self.request('/api/email-preview',body={'case_id':case_id,'kind':'customer'})[0],400)
        self.assertEqual(self.request('/api/email-send',body={'outbox_id':'unknown','reviewer':'Tester','acknowledged':False})[0],400)


if __name__=='__main__':unittest.main()
