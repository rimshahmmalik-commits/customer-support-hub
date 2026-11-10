"""Run with python app.py, or press F5 in VS Code. Localhost only."""
import csv
import io
import json
import os
import threading
import webbrowser
import base64
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from hearthwood.config import ROOT,PRODUCTS,TEAMS,load_env
from hearthwood import storage
from hearthwood.providers import ProviderError,classify_openai
from hearthwood.reporting import build_report,report_markdown
from hearthwood.dashboard import build_dashboard
from hearthwood import images,messaging
from hearthwood.providers import extract_image
from hearthwood.intake_details import suggest_details
from hearthwood import gmail_setup
from hearthwood.triage import classify_rules,validate_input
from hearthwood import public_demo

load_env()
MAX_BODY=16000
APP_VERSION='2026.11.11.2'


class LocalHTTPServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can otherwise let two servers answer the same port.
    allow_reuse_address=False

    def server_bind(self):
        if os.name=='nt':
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()


def export_csv(cases):
    out=io.StringIO();writer=csv.writer(out)
    writer.writerow(['Case','Customer','Product','Category','Urgency','Proposed team','Engine','Status','Reviewer','Review note','Reviewed at','Draft'])
    for case in cases:
        r,c=case['result'],case['complaint']
        values=[case['id'],c.get('customer',''),c.get('product',''),r['category'],r['urgency'],r['team'],r['engine'],case['status'],case['reviewer'] or '',case['review_note'] or '',case['reviewed_at'] or '',r['draft']]
        writer.writerow(["'"+str(x) if str(x).startswith(('=','+','-','@','\t','\r')) else x for x in values])
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    def respond(self,body,code=200,ctype='application/json; charset=utf-8',filename=None):
        raw=body if isinstance(body,bytes) else body.encode('utf-8')
        self.send_response(code)
        for name,value in {'Content-Type':ctype,'Content-Length':str(len(raw)),
            'X-Content-Type-Options':'nosniff','Cache-Control':'no-store',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"}.items():
            self.send_header(name,value)
        if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        if getattr(self,'demo_cookie',None):
            secure='; Secure' if os.getenv('DEMO_HTTPS')=='1' else ''
            self.send_header('Set-Cookie','csh_demo='+self.demo_cookie+'; Path=/; HttpOnly; SameSite=Strict; Max-Age=5400'+secure)
        self.end_headers();self.wfile.write(raw)

    def data(self,data,code=200):
        self.respond(json.dumps(data,ensure_ascii=False),code)

    def trusted_host(self):
        if public_demo.enabled() and os.getenv('RENDER_EXTERNAL_HOSTNAME'):
            return self.headers.get('Host') in {os.environ['RENDER_EXTERNAL_HOSTNAME'],f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}

    def demo_dispatch(self,callback):
        if not public_demo.enabled():return callback()
        if not self.trusted_host():return self.data({'error':'Unknown demo host.'},403)
        if self.path=='/healthz':return self.data({'status':'ok','mode':'synthetic-demo'})
        try:
            with public_demo.manager().session(self.headers.get('Cookie','')) as cookie:
                self.demo_cookie=cookie
                return callback()
        except public_demo.DemoCapacityError as exc:return self.data({'error':str(exc)},503)

    def do_GET(self):return self.demo_dispatch(self.demo_GET)
    def do_POST(self):return self.demo_dispatch(self.demo_POST)

    def demo_GET(self):
        if not self.trusted_host():return self.data({'error':'Local host required.'},403)
        parsed=urlparse(self.path);path=parsed.path;query=parse_qs(parsed.query)
        assets={'/favicon.svg':('favicon.svg','image/svg+xml'),'/':('index.html','text/html; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8')}
        try:
            if path in assets:
                name,ctype=assets[path];return self.respond((ROOT/'web'/name).read_bytes(),ctype=ctype)
            if path=='/api/config':
                return self.data({'app_version':APP_VERSION,'image_limit_bytes':images.MAX_IMAGE_BYTES,
                                  'products':PRODUCTS,'teams':TEAMS,'model':os.getenv('OPENAI_MODEL','gpt-4.1-mini'),
                                  'key_configured':bool(os.getenv('OPENAI_API_KEY')) and (not public_demo.enabled() or os.getenv('DEMO_ENABLE_OPENAI')=='1'),'synthetic':True,
                                  'public_demo':public_demo.enabled(),
                                  'email':messaging.settings()})
            if path.startswith('/api/attachments/'):
                image=images.get(path.removeprefix('/api/attachments/'))
                return self.respond(base64.b64decode(image['data'].split(',',1)[1]),ctype=image['mime'])
            if path.startswith('/api/case-evidence/'):
                return self.data(images.for_case(path.removeprefix('/api/case-evidence/')))
            if path.startswith('/api/messages/'):
                return self.data(messaging.case_messages(path.removeprefix('/api/messages/')))
            if path=='/api/cases':return self.data(storage.cases())
            if path=='/api/events':return self.data(storage.events())
            if path=='/api/dashboard':
                source=query.get('source',['interactive'])[0]
                if source not in ('sample','interactive'):raise ValueError('Select sample or interactive records.')
                return self.data(build_dashboard(storage.cases(source),source))
            if path=='/api/report' or path=='/api/report.md':
                source=query.get('source',['sample'])[0]
                if source not in ('sample','interactive'):raise ValueError('Select sample or interactive records.')
                report=build_report(storage.cases(source),query.get('as_of',[None])[0])
                if path.endswith('.md'):return self.respond(report_markdown(report),ctype='text/markdown; charset=utf-8',filename='customer-support-insights.md')
                return self.data(report)
            if path=='/api/export.csv':
                return self.respond(export_csv(storage.cases('interactive')),ctype='text/csv; charset=utf-8',filename='customer-support-case-reviews.csv')
            return self.data({'error':'Not found.'},404)
        except ValueError as exc:return self.data({'error':str(exc)},400)
        except Exception:return self.data({'error':'Could not load the local data. Check the terminal and restart the app.'},500)

    def demo_POST(self):
        if not self.trusted_host():return self.data({'error':'Local host required.'},403)
        if public_demo.enabled() and self.path in {'/api/email-send','/api/gmail-configure','/api/gmail-test'}:
            return self.data({'error':'Email sending and account connections are disabled in this public demo. Preview only.'},403)
        origin=self.headers.get('Origin')
        allowed_origins={f'http://localhost:{self.server.server_port}',f'http://127.0.0.1:{self.server.server_port}'}
        if public_demo.enabled() and os.getenv('RENDER_EXTERNAL_HOSTNAME'):
            allowed_origins.add('https://'+os.environ['RENDER_EXTERNAL_HOSTNAME'])
        if origin and origin not in allowed_origins:
            return self.data({'error':'Cross-site requests are not accepted.'},403)
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            return self.data({'error':'Use application/json.'},415)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<=0:return self.data({'error':'Empty request.'},400)
            limit=2_800_000 if self.path=='/api/images' else MAX_BODY
            if length>limit:return self.data({'error':'Request is too large.'},413)
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict):raise ValueError('Expected an object.')
            if public_demo.enabled() and self.path=='/api/demo/reset':
                public_demo.manager().reset();return self.data({'message':'Your synthetic session was reset. No other visitor was affected.'})
            if public_demo.enabled() and body.get('api_key'):
                raise ValueError('Do not enter API credentials into the public demo.')
            if self.path=='/api/suggest-details':
                return self.data(suggest_details(body.get('text')))
            if self.path=='/api/gmail-configure':
                return self.data(gmail_setup.configure(body.get('address'),body.get('app_password')))
            if self.path=='/api/gmail-test':
                return self.data(gmail_setup.test_connection())
            if self.path=='/api/images':
                if public_demo.enabled():
                    with storage.db() as con:
                        if con.execute('SELECT count(*) FROM attachments').fetchone()[0]>=8:raise ValueError('Image allowance reached. Reset your demo session to start again.')
                return self.data(images.upload(body.get('data'),body.get('name')),201)
            if self.path=='/api/extract-image':
                image=images.get(body.get('image_id',''))
                supplied=body.get('api_key','')
                if not isinstance(supplied,str) or len(supplied)>500:raise ValueError('Invalid API key field.')
                if public_demo.enabled():
                    public_demo.manager().reserve_ai_call()
                try:
                    result=extract_image(image['data'],supplied.strip() or os.getenv('OPENAI_API_KEY',''),(os.getenv('OPENAI_MODEL','gpt-4.1-mini') if public_demo.enabled() else body.get('model') or os.getenv('OPENAI_MODEL','gpt-4.1-mini')))
                except ProviderError as exc:
                    storage.record_failure('OpenAI image extraction',str(exc))
                    return self.data({'error':str(exc)},502)
                images.save_extraction(image['id'],result['text'])
                return self.data(result)
            if self.path=='/api/email-preview':
                return self.data(messaging.preview(body.get('case_id',''),body.get('kind','')))
            if self.path=='/api/email-send':
                return self.data(messaging.submit(body.get('outbox_id',''),body.get('reviewer'),body.get('acknowledged')))
            if self.path=='/api/triage':
                if public_demo.enabled() and len(storage.cases('interactive'))>=28:raise ValueError('Case allowance reached. Reset your session to start again.')
                complaint=validate_input(body.get('complaint'))
                image_id=body.get('image_id')
                if image_id:
                    image=images.get(image_id)
                    if image['case_id']:raise ValueError('This image is already attached. Upload it again for a new case.')
                    if image['extracted_text'] is not None and body.get('image_text_reviewed') is not True:
                        raise ValueError('Review the extracted image text and confirm it before triage.')
                engine=body.get('engine','rules')
                if engine not in ('rules','openai'):raise ValueError('Select Offline rules or OpenAI.')
                if engine=='openai':
                    supplied=body.get('api_key','')
                    if not isinstance(supplied,str) or len(supplied)>500:raise ValueError('Invalid API key field.')
                    model=os.getenv('OPENAI_MODEL','gpt-4.1-mini') if public_demo.enabled() else body.get('model') or os.getenv('OPENAI_MODEL','gpt-4.1-mini')
                    if public_demo.enabled():public_demo.manager().reserve_ai_call()
                    try:result=classify_openai(complaint,supplied.strip() or os.getenv('OPENAI_API_KEY',''),model)
                    except ProviderError as exc:
                        reason=str(exc);storage.record_failure('OpenAI',reason)
                        if body.get('allow_fallback') is not True:return self.data({'error':reason,'can_fallback':True},502)
                        result=classify_rules(complaint);result['fallback_reason']=reason
                        result['uncertain']=True;result['reason']='OpenAI failed. This is a rule-based suggestion and needs checking.'
                else:result=classify_rules(complaint)
                return self.data(storage.create_case(complaint,result,image_id),201)
            if self.path.startswith('/api/review/'):
                return self.data(storage.review(self.path.removeprefix('/api/review/'),body))
            return self.data({'error':'Not found.'},404)
        except (ValueError,TypeError,UnicodeError):
            # JSON decode errors are deliberately handled rather than breaking the connection.
            import sys
            exc=sys.exc_info()[1]
            return self.data({'error':str(exc) if not isinstance(exc,json.JSONDecodeError) else 'Malformed JSON request.'},400)
        except Exception:return self.data({'error':'The request could not be saved. No approval was confirmed.'},500)


def main():
    if not public_demo.enabled():
        storage.init();images.init();messaging.init();storage.seed_history()
    port=int(os.getenv('PORT',os.getenv('HEARTHWOOD_PORT','8004')))
    try:
        server=LocalHTTPServer(('0.0.0.0' if public_demo.enabled() else '127.0.0.1',port),Handler)
    except OSError as exc:
        raise SystemExit(f'Cannot start Customer Support Hub on port {port}: another app may already be running. '
                         f'Open http://127.0.0.1:{port} or stop that copy first. ({exc})') from None
    url=f'http://127.0.0.1:{port}'
    print(f'Customer Support Hub is running at {url}',flush=True)
    print(f'Version {APP_VERSION} | App folder: {ROOT}',flush=True)
    print('Local support workspace. Ctrl+C stops the service. Email requires configured SMTP and explicit approval.',flush=True)
    if not public_demo.enabled() and os.getenv('HEARTHWOOD_OPEN_BROWSER','1') != '0':
        opener=threading.Timer(0.5,webbrowser.open,args=(url,))
        opener.daemon=True
        opener.start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
