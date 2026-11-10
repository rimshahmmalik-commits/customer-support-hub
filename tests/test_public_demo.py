import json,os,tempfile,threading,unittest,urllib.request,urllib.error
from http.cookiejar import CookieJar
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from hearthwood.public_demo import DemoSessions,REQUEST_DATABASE
from hearthwood import storage,images,messaging,gmail_setup
from hearthwood.triage import classify_rules
from app import Handler

class PublicDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.manager=DemoSessions(Path(self.temp.name)/'sessions')
        self.env=patch.dict(os.environ,{'DEMO_PUBLIC':'1','DEMO_HTTPS':'0','DEMO_ENABLE_OPENAI':'0','RENDER_EXTERNAL_HOSTNAME':''});self.env.start()
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def add(self):
        c={'message':'The table arrived broken.','customer':'Demo visitor'}
        return storage.create_case(c,classify_rules(c))
    def test_visitors_have_independent_cases_and_reviews(self):
        with self.manager.session('') as a:
            new=self.add();self.assertEqual(len(storage.cases('interactive')),9)
        with self.manager.session('') as b:
            self.assertNotEqual(a,b);self.assertEqual(len(storage.cases('interactive')),8)
            with self.assertRaises(ValueError):storage.get_case(new['id'])
        with self.manager.session('csh_demo='+a):self.assertEqual(len(storage.cases('interactive')),9)
        self.assertIsNone(REQUEST_DATABASE.get())
    def test_reset_affects_only_own_session(self):
        with self.manager.session('') as a:self.add()
        with self.manager.session('') as b:self.add();self.add()
        with self.manager.session('csh_demo='+a):self.manager.reset();self.assertEqual(len(storage.cases('interactive')),8)
        with self.manager.session('csh_demo='+b):self.assertEqual(len(storage.cases('interactive')),10)
    def test_modified_cookie_cannot_select_existing_database(self):
        with self.manager.session('') as token:self.add()
        tampered=token[:-1]+('a' if token[-1]!='a' else 'b')
        with self.manager.session('csh_demo='+tampered) as other:self.assertNotEqual(token,other);self.assertEqual(len(storage.cases('interactive')),8)
    def test_public_helpers_cannot_connect_accounts_or_send_mail(self):
        with self.assertRaises(ValueError):gmail_setup.configure('test@gmail.com','abcdefghijklmnop')
        with self.assertRaises(ValueError):gmail_setup.test_connection()
        with self.assertRaises(ValueError):messaging.submit('none','Tester',True)
        self.assertFalse(messaging.settings()['configured'])
    def test_live_ai_disabled_without_owner_configuration(self):
        with self.manager.session(''):
            with self.assertRaisesRegex(ValueError,'not configured'):self.manager.reserve_ai_call()
    def test_attachment_ids_are_private_to_session(self):
        from test_operations import PNG
        with self.manager.session('') as token:image=images.upload(PNG,'test.png')
        with self.manager.session(''):
            with self.assertRaises(ValueError):images.get(image['id'])
        with self.manager.session('csh_demo='+token):self.assertEqual(images.get(image['id'])['name'],'test.png')
    def test_http_sessions_health_and_blocked_mail_endpoints(self):
        with patch('hearthwood.public_demo.manager',return_value=self.manager):
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(server.server_port)
            one=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
            two=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
            try:
                with one.open(base+'/healthz') as response:self.assertEqual(response.status,200)
                self.assertEqual(len(list(self.manager.root.glob('*.sqlite3'))),0)
                with one.open(base+'/api/config') as response:
                    self.assertTrue(json.load(response)['public_demo']);self.assertIn('HttpOnly',response.headers['Set-Cookie'])
                body=json.dumps({'complaint':{'message':'My refund is missing.'},'engine':'rules'}).encode()
                with one.open(urllib.request.Request(base+'/api/triage',data=body,headers={'Content-Type':'application/json'})) as response:self.assertEqual(response.status,201)
                with two.open(base+'/api/cases') as response:self.assertEqual(len([c for c in json.load(response) if c['source']=='interactive']),8)
                for endpoint in ['/api/email-send','/api/gmail-configure','/api/gmail-test']:
                    with self.assertRaises(urllib.error.HTTPError) as caught:one.open(urllib.request.Request(base+endpoint,data=b'{}',headers={'Content-Type':'application/json'}))
                    self.assertEqual(caught.exception.code,403)
            finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
