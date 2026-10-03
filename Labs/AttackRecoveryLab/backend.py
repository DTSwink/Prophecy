"""Local desktop identity, exact view capture and permanent variant exclusions."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
import argparse
import base64
import hashlib
import json
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parent
STORE = ROOT
LOCK = threading.RLock()
SESSION = {}
LIVE = None
LIVE_IMAGE = None
COMMANDS = []

def now():
    return datetime.now(timezone.utc).isoformat()

def atomic_json(path, value):
    raw = json.dumps(value, indent=2, allow_nan=False).encode()
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(raw)
    temporary.replace(path)

def read_json(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def revision():
    digest = hashlib.sha256()
    for name in ('index.html', 'app.js', 'recovery.js', 'style.css', 'renderer.js'):
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()

def manifest():
    data = read_json(ROOT / 'data/manifest.json', {})
    exclusions = read_json(STORE / 'removed_variants.json', {})
    for clip in data['clips']:
        clip['variants'] = [v for v in clip['variants'] if f"{clip['name']}:{v['id']}" not in exclusions]
    data['clips'] = [c for c in data['clips'] if c['variants']]
    data['removedCount'] = len(exclusions)
    return data

def image_bytes(value):
    data = base64.b64decode(value.split(',', 1)[1], validate=True)
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Expected PNG')
    return data

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        if len(args) > 1 and str(args[1]) not in ('200', '304'):
            super().log_message(fmt, *args)

    def response(self, raw, content_type='application/json', status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def json_response(self, value, status=200):
        self.response(json.dumps(value, allow_nan=False).encode(), status=status)

    def is_desktop(self):
        token = self.headers.get('X-Desktop-Session')
        client = self.headers.get('X-Client-Id')
        if not token or token != SESSION.get('token') or not client:
            return False
        if SESSION.get('clientId') is None:
            SESSION['clientId'] = client
            atomic_json(STORE / 'desktop_session.json', SESSION)
        return SESSION.get('clientId') == client

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        with LOCK:
            if path == '/health':
                return self.json_response({'app':'attack-recovery-lab','root':str(ROOT),'store':str(STORE),'revision':revision(),'apiVersion':2})
            if path == '/state':
                return self.json_response(read_json(STORE / 'state.json', {}))
            if path == '/data/manifest.json':
                return self.json_response(manifest())
            if path == '/snapshots':
                return self.json_response(sorted([p.stem for p in (STORE / 'snapshots').glob('snapshot_*.json')], reverse=True))
            if path.startswith('/snapshots/'):
                filename = path.removeprefix('/snapshots/')
                if '/' in filename or '\\' in filename or not filename.startswith('snapshot_'):
                    return self.json_response({'error':'invalid snapshot'},400)
                target = STORE / 'snapshots' / filename
                if not target.is_file():
                    return self.json_response({'error':'snapshot missing'},404)
                return self.response(target.read_bytes(), 'image/png' if target.suffix == '.png' else 'application/json')
            if path == '/desktop-view':
                return self.json_response({'ok':LIVE is not None, **(LIVE or {})})
            if path == '/desktop-view.png':
                sequence = parse_qs(parsed.query).get('sequence', [''])[0]
                if not LIVE or (sequence and sequence != str(LIVE['sequence'])):
                    return self.json_response({'error':'view changed; reread desktop-view'},409)
                return self.response(LIVE_IMAGE, 'image/png')
            if path == '/capture':
                identity = parse_qs(parsed.query).get('id',[''])[0]
                if not identity or any(c not in '0123456789abcdef' for c in identity):
                    return self.json_response({'error':'invalid capture id'},400)
                result = read_json(STORE / 'captures' / (identity+'.json'), None)
                return self.json_response(result or {'pending':True})
        if path in ('/', '/index.html'):
            html = (ROOT / 'index.html').read_text(encoding='utf-8').replace('__BUILD_REVISION__', revision())
            return self.response(html.encode(), 'text/html; charset=utf-8')
        if path in ('/desktop_session.json', '/state.json', '/removed_variants.json'):
            return self.json_response({'error':'private app metadata'},403)
        return super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def do_POST(self):
        global LIVE, LIVE_IMAGE, SESSION
        origin = self.headers.get('Origin')
        if origin and origin != f'http://{self.headers.get("Host")}':
            return self.json_response({'error':'origin mismatch'},403)
        size = int(self.headers.get('Content-Length','0'))
        if not 0 < size <= 16*1024*1024:
            return self.json_response({'error':'invalid body size'},400)
        try:
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict):
                raise ValueError('Expected an object')
            with LOCK:
                if self.path == '/desktop-session':
                    token = str(value.get('token',''))
                    if len(token) < 24:
                        raise ValueError('Invalid desktop session')
                    SESSION = {'token':token,'clientId':None,'registeredAt':now()}
                    atomic_json(STORE / 'desktop_session.json', SESSION)
                    LIVE = LIVE_IMAGE = None
                    COMMANDS.clear()
                    return self.json_response({'ok':True})
                if self.path == '/app-control':
                    if not LIVE or value.get('clientId') != LIVE['clientId']:
                        raise ValueError('No matching desktop client')
                    if value.get('command') != 'capture_visible_trajectory':
                        raise ValueError('Only read-only trajectory capture is supported')
                    command = {'id':uuid.uuid4().hex,'command':value['command'],'fingerprint':LIVE['fingerprint']}
                    COMMANDS.append(command)
                    return self.json_response({'ok':True,**command})
                if not self.is_desktop():
                    return self.json_response({'error':'only the registered desktop client may publish or save'},403)
                if self.path == '/state':
                    atomic_json(STORE / 'state.json', value)
                    return self.json_response({'ok':True})
                if self.path == '/desktop-view':
                    sequence = int(value['sequence'])
                    if LIVE and sequence <= LIVE['sequence']:
                        return self.json_response({'ok':True,'stale':True})
                    if 'image' in value:
                        png = image_bytes(value.pop('image'))
                    elif LIVE and value.get('fingerprint') == LIVE['fingerprint']:
                        png = LIVE_IMAGE
                    else:
                        raise ValueError('A changed view needs its matching image')
                    value.update({'clientId':SESSION['clientId'],'receivedAt':now(), 'imageSha256':hashlib.sha256(png).hexdigest()})
                    LIVE, LIVE_IMAGE = value, png
                    (STORE / 'current_view.png').write_bytes(png)
                    atomic_json(STORE / 'current_view.json', value)
                    commands = list(COMMANDS)
                    COMMANDS.clear()
                    return self.json_response({'ok':True,'commands':commands})
                if self.path == '/capture':
                    identity = str(value.get('id',''))
                    if len(identity)!=32 or any(c not in '0123456789abcdef' for c in identity):
                        raise ValueError('Invalid capture id')
                    directory = STORE / 'captures'
                    directory.mkdir(exist_ok=True)
                    value.update({'clientId':SESSION['clientId'],'receivedAt':now()})
                    atomic_json(directory / (identity+'.json'), value)
                    return self.json_response({'ok':True})
                if self.path == '/remove-variant':
                    data = read_json(ROOT / 'data/manifest.json', {})
                    clip = next((c for c in data['clips'] if c['name']==value.get('attack')), None)
                    variant = next((v for v in clip['variants'] if v['id']==value.get('variant')), None) if clip else None
                    if not variant or variant['sha256'] != value.get('motionSha'):
                        raise ValueError('Unknown variant or motion changed')
                    removed = read_json(STORE / 'removed_variants.json', {})
                    key = f"{clip['name']}:{variant['id']}"
                    removed.setdefault(key, {'attack':clip['name'],'variant':variant['id'], 'motionSha':variant['sha256'],'removedAt':now(),'sourceSha':variant['sourceSha']})
                    atomic_json(STORE / 'removed_variants.json', removed)
                    return self.json_response({'ok':True,'removed':removed[key]})
                if self.path == '/snapshot':
                    directory = STORE / 'snapshots'
                    directory.mkdir(exist_ok=True)
                    number = max([int(p.stem.split('_')[-1]) for p in directory.glob('snapshot_*.json')], default=0)+1
                    stem = f'snapshot_{number:04d}'
                    png = image_bytes(value.pop('image'))
                    value.update({'capturedAt':now(),'clientId':SESSION['clientId']})
                    (directory / f'{stem}.png').write_bytes(png)
                    atomic_json(directory / f'{stem}.json',value)
                    return self.json_response({'ok':True,'name':stem})
            return self.json_response({'error':'unknown endpoint'},404)
        except (ValueError,KeyError,TypeError) as error:
            return self.json_response({'error':str(error)},400)

def main():
    global STORE, SESSION
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8817)
    parser.add_argument('--state-dir',type=Path,default=ROOT)
    args=parser.parse_args()
    STORE=args.state_dir.resolve()
    STORE.mkdir(parents=True,exist_ok=True)
    SESSION=read_json(STORE/'desktop_session.json',{})
    if sys.stdout is None:sys.stdout=(STORE/'server.stdout.log').open('a',encoding='utf-8')
    if sys.stderr is None:sys.stderr=(STORE/'server.stderr.log').open('a',encoding='utf-8')
    print(f'Attack Recovery Lab http://127.0.0.1:{args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

if __name__ == '__main__':
    main()
