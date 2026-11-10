"""Private Gmail SMTP setup for the local app; no chat credentials or automatic sending."""
import os
import re
import smtplib
import ssl
import uuid
from .config import ROOT
from .messaging import valid_email,settings
from . import storage


def configure(address,password):
    if not isinstance(address,str) or not valid_email(address.strip()):
        raise ValueError('Enter your full Gmail address.')
    address=address.strip()
    if not isinstance(password,str):
        raise ValueError('Enter a Google app password in the private field.')
    password=password.replace(' ','').strip()
    if not re.fullmatch(r'[A-Za-z0-9]{16}',password):
        raise ValueError('Use the 16-character Google app password, not your normal account password.')
    values={'SMTP_HOST':'smtp.gmail.com','SMTP_PORT':'587','SMTP_USER':address,
            'SMTP_FROM':address,'SMTP_PASSWORD':password}
    env_file=ROOT/'.env'
    existing=env_file.read_text(encoding='utf-8-sig').splitlines() if env_file.exists() else []
    kept=[line for line in existing if line.split('=',1)[0].strip() not in values]
    content='\n'.join(kept+['']+[name+'='+value for name,value in values.items()])+'\n'
    temporary=ROOT/('.env.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x',encoding='utf-8') as output:
            output.write(content)
        os.replace(temporary,env_file)
    finally:
        if temporary.exists():temporary.unlink()
    os.environ.update(values)
    with storage.db() as con:
        storage.audit(con,None,'email_connection_configured',{'provider':'Gmail','sender':address,'authentication_tested':False})
    return {'message':'Gmail settings saved privately. Test the connection before sending. No email was sent.',
            'email':settings()}


def test_connection():
    cfg=settings()
    if not cfg['configured'] or os.getenv('SMTP_HOST')!='smtp.gmail.com':
        raise ValueError('Save your Gmail connection first.')
    try:
        with smtplib.SMTP('smtp.gmail.com',587,timeout=20) as client:
            client.ehlo();client.starttls(context=ssl.create_default_context());client.ehlo()
            client.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
    except smtplib.SMTPAuthenticationError:
        raise ValueError('Gmail rejected the login. Check the account and Google app password; do not use your regular password.') from None
    except (OSError,smtplib.SMTPException):
        raise ValueError('Gmail could not be reached or the connection failed. No email was sent.') from None
    with storage.db() as con:
        storage.audit(con,None,'email_connection_tested',{'provider':'Gmail','sender':cfg['sender'],'authenticated':True,'email_sent':False})
    return {'message':'Gmail authentication succeeded. No email was sent. You can now test a reviewed message to your own address.'}
