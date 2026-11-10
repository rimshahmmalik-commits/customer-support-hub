"""Local image evidence and explicit, reviewable screenshot transcription."""
import base64
import binascii
import hashlib
import re
import uuid
from . import storage

MAX_IMAGE_BYTES=2_000_000


def init():
    with storage.db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS attachments (
            id TEXT PRIMARY KEY, case_id TEXT, name TEXT NOT NULL, mime TEXT NOT NULL,
            data TEXT NOT NULL, sha256 TEXT NOT NULL, extracted_text TEXT,
            created_at TEXT NOT NULL)''')


def upload(data_url,name):
    if not isinstance(name,str) or not 1<=len(name)<=160:
        raise ValueError('Enter an image filename up to 160 characters.')
    if not isinstance(data_url,str):
        raise ValueError('Select a PNG or JPEG image.')
    match=re.fullmatch(r'data:(image/(?:png|jpeg));base64,([A-Za-z0-9+/=]+)',data_url)
    if not match:
        raise ValueError('Only PNG or JPEG image evidence is accepted.')
    try:
        raw=base64.b64decode(match[2],validate=True)
    except (ValueError,binascii.Error):
        raise ValueError('The image encoding is invalid.') from None
    if not 32<=len(raw)<=MAX_IMAGE_BYTES:
        raise ValueError('Choose an image no larger than 2 MB.')
    if (match[1]=='image/png' and not raw.startswith(b'\x89PNG\r\n\x1a\n')) or (match[1]=='image/jpeg' and not raw.startswith(b'\xff\xd8\xff')):
        raise ValueError('The file content does not match its image type.')
    image_id=uuid.uuid4().hex
    with storage.db() as con:
        con.execute('INSERT INTO attachments VALUES (?,?,?,?,?,?,?,?)',
                    (image_id,None,name,match[1],data_url,hashlib.sha256(raw).hexdigest(),None,storage.now()))
    return {'id':image_id,'name':name,'url':'/api/attachments/'+image_id,'bytes':len(raw)}


def get(image_id):
    with storage.db() as con:
        row=con.execute('SELECT * FROM attachments WHERE id=?',(image_id,)).fetchone()
    if not row:
        raise ValueError('Image evidence not found.')
    return dict(row)


def for_case(case_id):
    with storage.db() as con:
        rows=con.execute('SELECT id,name,mime,sha256,created_at FROM attachments WHERE case_id=?',(case_id,))
        return [{**dict(row),'url':'/api/attachments/'+row['id']} for row in rows]


def save_extraction(image_id,text):
    with storage.db() as con:
        con.execute('UPDATE attachments SET extracted_text=? WHERE id=?',(text,image_id))
        storage.audit(con,None,'image_text_extracted',{'image_id':image_id,'characters':len(text),'review_required':True})
