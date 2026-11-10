"""Streamlit transport for the existing HTTP handlers; no second web server."""
import base64
import io
import json
from types import SimpleNamespace
from urllib.parse import urlparse
from . import public_demo, images


def dispatch(command, cookie=''):
    if not public_demo.enabled():
        raise RuntimeError('The component adapter requires public demo mode.')
    from app import Handler
    if not isinstance(command, dict) or not isinstance(command.get('id'), str):
        raise ValueError('Invalid component command.')
    path = command.get('path', '')
    if not isinstance(path, str) or not path.startswith('/api/') or urlparse(path).netloc:
        raise ValueError('Only local demo API calls are supported.')
    method = command.get('method', 'GET')
    if method not in ('GET', 'POST'):
        raise ValueError('Unsupported method.')
    raw = json.dumps(command.get('body', {})).encode('utf-8')
    if len(raw) > 2_800_000:
        raise ValueError('Request is too large.')

    class Request(Handler):
        def __init__(self):
            self.path = path
            self.server = SimpleNamespace(server_port=0)
            self.headers = {'Host': 'localhost:0', 'Content-Type': 'application/json', 'Content-Length': str(len(raw))}
            self.rfile = io.BytesIO(raw)
            self.result = None
        def respond(self, body, code=200, ctype='application/json; charset=utf-8', filename=None):
            if ctype.startswith('application/json'):
                data = json.loads(body)
                def inline(value):
                    if isinstance(value, dict):
                        value = {k: inline(v) for k, v in value.items()}
                        if isinstance(value.get('url'), str) and value['url'].startswith('/api/attachments/'):
                            value['url'] = images.get(value['url'].rsplit('/', 1)[-1])['data']
                    elif isinstance(value, list):
                        value = [inline(v) for v in value]
                    return value
                data = inline(data)
            elif filename:
                data = {'download': {'text': body.decode('utf-8') if isinstance(body, bytes) else body, 'mime': ctype, 'filename': filename}}
            else:
                data = {'error': 'This resource is unavailable in the hosted demo.'}
                code = 404
            self.result = {'id': command['id'], 'ok': 200 <= code < 300, 'data': data}

    with public_demo.manager().session(cookie) as signed:
        request = Request()
        (request.demo_GET if method == 'GET' else request.demo_POST)()
        return request.result, 'csh_demo=' + signed
