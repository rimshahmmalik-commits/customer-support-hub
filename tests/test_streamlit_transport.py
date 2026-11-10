import os
import tempfile
import unittest
from unittest.mock import patch

class StreamlitTransportTests(unittest.TestCase):
    def setUp(self):
        from hearthwood import public_demo
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'DEMO_PUBLIC':'1','DEMO_ENABLE_OPENAI':'0'})
        self.env.start()
        self.manager = patch.object(public_demo, '_manager', public_demo.DemoSessions(self.tmp.name))
        self.manager.start()
    def tearDown(self):
        self.manager.stop(); self.env.stop(); self.tmp.cleanup()
    def call(self, path, body=None, cookie=''):
        from hearthwood.streamlit_transport import dispatch
        return dispatch({'id':'test','path':path,'method':'GET' if body is None else 'POST','body':body}, cookie)
    def test_real_handlers_and_private_sessions(self):
        a, cookie = self.call('/api/cases')
        self.assertEqual(len([x for x in a['data'] if x['source']=='interactive']),8)
        row, _ = self.call('/api/triage', {'complaint':{'customer':'Demo','message':'My refund has not arrived after returning the wardrobe.'},'engine':'rules'}, cookie)
        self.assertTrue(row['ok'], row)
        self.assertEqual(len([x for x in self.call('/api/cases',cookie=cookie)[0]['data'] if x['source']=='interactive']),9)
        self.assertEqual(len([x for x in self.call('/api/cases')[0]['data'] if x['source']=='interactive']),8)
        self.call('/api/demo/reset',{},cookie)
        self.assertEqual(len([x for x in self.call('/api/cases',cookie=cookie)[0]['data'] if x['source']=='interactive']),8)
    def test_downloads_and_blocked_delivery(self):
        export, cookie = self.call('/api/export.csv')
        self.assertIn('Case,Customer',export['data']['download']['text'])
        result,_ = self.call('/api/email-send',{},cookie)
        self.assertFalse(result['ok'])
    def test_rejects_external_paths(self):
        from hearthwood.streamlit_transport import dispatch
        with self.assertRaises(ValueError):
            dispatch({'id':'x','path':'https://example.com','method':'GET'})

