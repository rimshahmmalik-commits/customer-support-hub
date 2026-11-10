"""Public, isolated synthetic sessions. No credentials, mail delivery or shared customer state."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime,timedelta,timezone
import hashlib,hmac,json,os,re,secrets,sqlite3,tempfile,threading,time
from pathlib import Path
from http.cookies import SimpleCookie
from .config import ROOT

REQUEST_DATABASE=ContextVar('public_demo_database',default=None)

def enabled():return os.getenv('DEMO_PUBLIC')=='1'

class DemoCapacityError(ValueError):pass

class DemoSessions:
    def __init__(self,root=None,ttl=5400,limit=30):
        self.root=Path(root or os.getenv('DEMO_SESSION_DIR',Path(tempfile.gettempdir())/'customer-support-demo'))
        self.root.mkdir(parents=True,exist_ok=True)
        self.ttl=ttl;self.limit=limit;self.secret=secrets.token_bytes(32);self.lock=threading.RLock();self.seen={}
    def sign(self,sid):return sid+'.'+hmac.new(self.secret,sid.encode(),hashlib.sha256).hexdigest()
    def read(self,cookie):
        jar=SimpleCookie()
        try:jar.load(cookie or '');value=jar['csh_demo'].value
        except Exception:return None
        if not re.fullmatch(r'[a-f0-9]{32}\.[a-f0-9]{64}',value):return None
        sid=value.split('.')[0]
        return sid if hmac.compare_digest(value,self.sign(sid)) else None
    def cleanup(self):
        now=time.time()
        for path in self.root.glob('*.sqlite3'):
            if now-self.seen.get(path.stem,path.stat().st_mtime)>self.ttl:
                path.unlink(missing_ok=True);self.seen.pop(path.stem,None)
    @contextmanager
    def session(self,cookie):
        with self.lock:
            self.cleanup();sid=self.read(cookie)
            if not sid or not (self.root/(sid+'.sqlite3')).exists():
                if len(list(self.root.glob('*.sqlite3')))>=self.limit:
                    raise DemoCapacityError('The demo is busy. Please try again later.')
                sid=secrets.token_hex(16)
            path=self.root/(sid+'.sqlite3');token=REQUEST_DATABASE.set(path)
            try:
                if not path.exists():self.seed()
                self.seen[sid]=time.time()
                yield self.sign(sid)
            finally:REQUEST_DATABASE.reset(token)
    def seed(self):
        from . import storage,images,messaging
        from .triage import validate_input,classify_rules
        storage.init();images.init();messaging.init();storage.seed_history()
        now=datetime.now(timezone.utc)
        fixture=json.loads((ROOT/'data/demo_cases.json').read_text(encoding='utf-8'))
        with storage.db() as con:
            for i,item in enumerate(fixture['cases'],1):
                complaint=validate_input(item);created=(now-timedelta(hours=item['age_hours'])).isoformat(timespec='seconds')
                complaint.update(synthetic=True,date=created[:10]);result=classify_rules(complaint)
                case_id=f'HW-DEMO-{i:03d}'
                con.execute('INSERT INTO cases(id,created_at,source,complaint,result,original_result,status) VALUES (?,?,?,?,?,?,?)',
                    (case_id,created,'interactive',json.dumps(complaint),json.dumps(result),json.dumps(result),'pending'))
                storage.audit(con,case_id,'synthetic_demo_case_created',{'synthetic':True,'fictional_intake_date':True,'engine':result['engine']})
    def reset(self):
        from . import storage
        with storage.db() as con:
            for table in ('outbox','attachments','audit','cases'):con.execute('DELETE FROM '+table)
        self.seed()
    def reserve_ai_call(self):
        if os.getenv('DEMO_ENABLE_OPENAI')!='1' or not os.getenv('OPENAI_API_KEY'):
            raise ValueError('Live OpenAI is not configured for this public demo. Choose Offline keyword rules.')
        session_id=Path(REQUEST_DATABASE.get()).stem;day=datetime.now(timezone.utc).date().isoformat()
        with sqlite3.connect(self.root/'quota.db',timeout=10) as con:
            con.execute('CREATE TABLE IF NOT EXISTS calls(day TEXT,session TEXT,n INTEGER,PRIMARY KEY(day,session))')
            con.execute('BEGIN IMMEDIATE')
            total=con.execute('SELECT coalesce(sum(n),0) FROM calls WHERE day=?',(day,)).fetchone()[0]
            used=con.execute('SELECT n FROM calls WHERE day=? AND session=?',(day,session_id)).fetchone()
            if total>=20 or (used and used[0]>=3):raise ValueError('The demo AI allowance is used up. Offline mode still works.')
            con.execute('INSERT INTO calls VALUES (?,?,1) ON CONFLICT(day,session) DO UPDATE SET n=n+1',(day,session_id))

_manager=None
def manager():
    global _manager
    if _manager is None:_manager=DemoSessions()
    return _manager
