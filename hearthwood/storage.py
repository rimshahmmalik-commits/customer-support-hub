"""SQLite persistence for human review and audit history; no message-sending code."""
import csv
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import ROOT, TEAMS, CATEGORIES, database_path
from .triage import classify_rules, draft_issues


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@contextmanager
def db():
    path = database_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    con = sqlite3.connect(path,timeout=15)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init():
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source TEXT NOT NULL,
            complaint TEXT NOT NULL, result TEXT NOT NULL, original_result TEXT NOT NULL,
            status TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0,
            reviewer TEXT, review_note TEXT, reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, case_id TEXT,
            action TEXT NOT NULL, details TEXT NOT NULL);
        ''')


def audit(con, case_id, action, details):
    con.execute('INSERT INTO audit(at,case_id,action,details) VALUES (?,?,?,?)',
                (now(),case_id,action,json.dumps(details)))


def seed_history():
    with db() as con, (ROOT/'data/complaints.csv').open(encoding='utf-8') as source:
        for row in csv.DictReader(source):
            case_id = row['id']
            # Ground truth stays outside the app's classification input and response.
            complaint = {k:v for k,v in row.items() if k != 'true_category'}
            result = classify_rules(complaint)
            con.execute('INSERT OR IGNORE INTO cases(id,created_at,source,complaint,result,original_result,status) VALUES (?,?,?,?,?,?,?)',
                (case_id,row['date']+'T12:00:00+00:00','sample',json.dumps(complaint),json.dumps(result),json.dumps(result),'sample'))


def unpack(row):
    result = dict(row)
    for name in ('complaint','result','original_result'):
        result[name] = json.loads(result[name])
    return result


def cases(source=None):
    with db() as con:
        if source:
            rows = con.execute('SELECT * FROM cases WHERE source=? ORDER BY created_at DESC,id DESC',(source,))
        else:
            rows = con.execute('SELECT * FROM cases ORDER BY created_at DESC,id DESC')
        return [unpack(x) for x in rows]


def get_case(case_id):
    with db() as con:
        row = con.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone()
    if not row:
        raise ValueError('Case not found.')
    return unpack(row)


def create_case(complaint,result,image_id=None):
    case_id = 'HW-C-' + uuid.uuid4().hex[:8].upper()
    with db() as con:
        if image_id:
            image=con.execute('SELECT case_id FROM attachments WHERE id=?',(image_id,)).fetchone()
            if not image or image['case_id']:
                raise ValueError('This image is unavailable or already attached to a case.')
            con.execute('UPDATE attachments SET case_id=? WHERE id=?',(case_id,image_id))
        con.execute('INSERT INTO cases(id,created_at,source,complaint,result,original_result,status) VALUES (?,?,?,?,?,?,?)',
                    (case_id,now(),'interactive',json.dumps(complaint),json.dumps(result),json.dumps(result),'pending'))
        audit(con,case_id,'triaged',{'engine':result['engine'],'model':result['model'],
              'category':result['category'],'safety_flag':result['safety_flag'],
              'fallback_reason':result.get('fallback_reason')})
    return get_case(case_id)


def record_failure(engine,error):
    with db() as con:
        audit(con,None,'triage_failed',{'engine':engine,'error':error})


def review(case_id, changes):
    if not isinstance(changes,dict):
        raise ValueError('Invalid review.')
    for name in ('category','urgency','draft','reviewer','note','decision'):
        if not isinstance(changes.get(name),str):
            raise ValueError(f'{name} must be text.')
    if type(changes.get('version')) is not int:
        raise ValueError('Missing review version. Reload the case.')
    if not changes['reviewer'].strip() or len(changes['reviewer'])>100:
        raise ValueError('Add a reviewer name, up to 100 characters.')
    if len(changes['note'])>2000 or len(changes['draft'])>6000:
        raise ValueError('Review note or draft is too long.')
    if changes['category'] not in CATEGORIES or changes['urgency'] not in ('urgent','normal','low'):
        raise ValueError('Select a valid category and urgency.')
    if changes['decision'] not in ('save','approve','reject'):
        raise ValueError('Invalid decision.')
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone()
        if not row or row['source']!='interactive':
            raise ValueError('Only newly submitted cases can be reviewed.')
        if row['status']!='pending':
            raise ValueError('This case has already been reviewed. No second decision was recorded.')
        if row['version']!=changes['version']:
            raise ValueError('This case changed in another window. Reload it before reviewing.')
        old = json.loads(row['result'])
        edited = any(changes[k]!=old[k] for k in ('category','urgency','draft'))
        if (edited or old['uncertain'] or old['safety_flag']) and not changes['note'].strip():
            raise ValueError('Explain your corrections or escalation in the review note.')
        if old['safety_flag'] and (changes['category']!='product_safety' or changes['urgency']!='urgent'):
            raise ValueError('A possible safety incident must stay urgent and routed to Product Safety.')
        if changes['decision']=='approve':
            if changes.get('acknowledged') is not True:
                raise ValueError('Confirm that you checked the complaint and draft.')
            if not changes['draft'].strip():
                raise ValueError('A draft cannot be empty.')
            issues = draft_issues(changes['draft'])
            if issues:
                raise ValueError(' '.join(issues))
        updated = {**old,'category':changes['category'],'urgency':changes['urgency'],
                   'team':TEAMS[changes['category']],'draft':changes['draft'].strip()}
        updated['safety_flag'] = old['safety_flag'] or changes['category']=='product_safety'
        if updated['safety_flag']:
            updated.update(urgency='urgent',team='Product Safety')
        updated['secondary'] = [x for x in updated['secondary'] if x!=updated['category']]
        status = {'save':'pending','approve':'approved','reject':'rejected'}[changes['decision']]
        con.execute('UPDATE cases SET result=?,status=?,version=version+1,reviewer=?,review_note=?,reviewed_at=? WHERE id=?',
            (json.dumps(updated),status,changes['reviewer'].strip(),changes['note'].strip(),now(),case_id))
        audit(con,case_id,'review_'+changes['decision'],{'reviewer':changes['reviewer'].strip(),
            'note':changes['note'].strip(),'before':old,'after':updated,'status':status})
    return get_case(case_id)


def events():
    with db() as con:
        return [dict(x) for x in con.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 500')]
