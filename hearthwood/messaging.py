"""Preview-first SMTP handoff with a durable, single-attempt outbox."""
import json
import os
import re
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from email.utils import make_msgid
from . import storage
from .config import CATEGORIES


def valid_email(value):
    return (isinstance(value,str) and len(value)<=254 and
            re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", value) is not None)


def settings():
    sender = os.getenv('SMTP_FROM','').strip()
    ready = bool(os.getenv('SMTP_HOST') and os.getenv('SMTP_USER') and os.getenv('SMTP_PASSWORD') and valid_email(sender))
    teams = {category: os.getenv('TEAM_EMAIL_'+category.upper(),'').strip() for category in CATEGORIES}
    return {'configured': ready, 'sender': sender if valid_email(sender) else '',
            'teams': {k:v for k,v in teams.items() if valid_email(v)}}


def init():
    with storage.db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS outbox (
            id TEXT PRIMARY KEY, case_id TEXT NOT NULL, version INTEGER NOT NULL,
            kind TEXT NOT NULL, recipient TEXT NOT NULL, subject TEXT NOT NULL,
            body TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL,
            sent_at TEXT, reviewer TEXT, message_id TEXT NOT NULL,
            UNIQUE(case_id,version,kind))''')


def case_messages(case_id):
    with storage.db() as con:
        return [dict(r) for r in con.execute(
            'SELECT * FROM outbox WHERE case_id=? ORDER BY created_at DESC',(case_id,))]


def preview(case_id,kind):
    if kind not in ('customer','department'):
        raise ValueError('Select customer or department email.')
    case=storage.get_case(case_id)
    if case['source']!='interactive':
        raise ValueError('Training records cannot be emailed.')
    if kind=='customer' and case['status']!='approved':
        raise ValueError('Approve the customer reply before preparing an email.')
    if kind=='department' and case['status']=='rejected':
        raise ValueError('Rejected cases cannot be emailed. Handle the escalation manually.')
    cfg=settings(); complaint=case['complaint']; result=case['result']
    recipient=complaint.get('customer_email','') if kind=='customer' else cfg['teams'].get(result['category'],'')
    if not valid_email(recipient):
        raise ValueError('A valid customer email is required at intake.' if kind=='customer'
                         else 'No department mailbox is configured for this category.')
    if kind=='customer':
        subject=f"Hearthwood Home | {case_id} | Your complaint"
        body=result['draft']
    else:
        subject=f"[{result['urgency'].upper()}] {case_id} | {result['team']} review"
        body=(f"Case: {case_id}\nOrder: {complaint.get('order_id') or 'Not supplied'}\n"
              f"Proposed team: {result['team']}\nUrgency: {result['urgency']}\n"
              f"Customer: {complaint.get('customer') or 'Not supplied'}\n"
              f"Product: {complaint.get('product') or 'Not supplied'}\n\n"
              f"Suggested summary (check against the source):\n{result['summary']}\n\n"
              f"Original complaint:\n{complaint['message']}\n\n"
              f"Review note: {case.get('review_note') or 'No review note recorded.'}\n\n"
              "Please review this case and record the action in the support system. "
              "No refund, replacement or customer resolution is confirmed by this handoff. "
              "Images are retained in the local case and are not attached to this email.")
    with storage.db() as con:
        con.execute('INSERT OR IGNORE INTO outbox VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (uuid.uuid4().hex,case_id,case['version'],kind,recipient,subject,body,'preview',storage.now(),None,None,make_msgid()))
        row=con.execute('SELECT * FROM outbox WHERE case_id=? AND version=? AND kind=?',
                        (case_id,case['version'],kind)).fetchone()
    return {**dict(row),'smtp_configured':cfg['configured']}


def submit(outbox_id,reviewer,acknowledged):
    if acknowledged is not True or not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>100:
        raise ValueError('Enter your reviewer name and confirm the recipient and message.')
    cfg=settings()
    if not cfg['configured']:
        raise ValueError('Email is not connected. Configure SMTP privately before sending.')
    try:
        port=int(os.getenv('SMTP_PORT','587'))
    except ValueError:
        raise ValueError('Use encrypted SMTP on port 465 or 587.') from None
    if port not in (465,587):
        raise ValueError('Use encrypted SMTP on port 465 or 587.')
    with storage.db() as con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM outbox WHERE id=?',(outbox_id,)).fetchone()
        if not row or row['state']!='preview':
            raise ValueError('This email was already attempted. Check its history before taking any further action.')
        case=con.execute('SELECT * FROM cases WHERE id=?',(row['case_id'],)).fetchone()
        if case['version']!=row['version'] or (row['kind']=='customer' and case['status']!='approved') or case['status']=='rejected':
            raise ValueError('The case changed. Open a new preview before sending.')
        # Freeze the exact message. A second click/request cannot attempt it again.
        con.execute("UPDATE outbox SET state='submitting',reviewer=? WHERE id=?",(reviewer.strip(),outbox_id))
        storage.audit(con,row['case_id'],'email_submitting',{'outbox_id':outbox_id,'kind':row['kind'],'recipient':row['recipient'],'reviewer':reviewer.strip()})
    message=EmailMessage();message['From']=cfg['sender'];message['To']=row['recipient']
    message['Subject']=row['subject'];message['Message-ID']=row['message_id'];message.set_content(row['body'])
    try:
        host=os.environ['SMTP_HOST']
        client=(smtplib.SMTP_SSL(host,port,timeout=20,context=ssl.create_default_context())
                if port==465 else smtplib.SMTP(host,port,timeout=20))
        with client:
            if port==587:
                client.ehlo();client.starttls(context=ssl.create_default_context());client.ehlo()
            client.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
            if client.send_message(message):
                raise OSError('Recipient not accepted.')
    except Exception:
        # A timeout can occur after provider acceptance. Never retry automatically.
        with storage.db() as con:
            con.execute("UPDATE outbox SET state='unknown' WHERE id=?",(outbox_id,))
            storage.audit(con,row['case_id'],'email_outcome_unknown',{'outbox_id':outbox_id})
        raise ValueError('Delivery could not be confirmed. Do not resend automatically: check the mailbox/provider log using the Message-ID.') from None
    with storage.db() as con:
        con.execute("UPDATE outbox SET state='submitted',sent_at=? WHERE id=?",(storage.now(),outbox_id))
        storage.audit(con,row['case_id'],'email_submitted',{'outbox_id':outbox_id,'message_id':row['message_id']})
    return {'state':'submitted','message':'Accepted by the mail server. This does not confirm inbox delivery.'}
