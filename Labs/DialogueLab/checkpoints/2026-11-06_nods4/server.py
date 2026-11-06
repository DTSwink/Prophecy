"""Dialogue Lab local service: static files + view snapshot (so Claude can see exactly what is on screen).
python server.py [--port 8842]   (binds 127.0.0.1 only)"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import argparse, base64, json

ROOT = Path(__file__).resolve().parent
APP = 'dialogue-lab'


class Handler(SimpleHTTPRequestHandler):
    # explicit types: on Windows the registry can map .js to text/plain, which blocks ES modules
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.js': 'text/javascript', '.json': 'application/json',
                      '.glb': 'model/gltf-binary', '.bin': 'application/octet-stream', '.png': 'image/png', '.mp3': 'audio/mpeg',
                      '.css': 'text/css', '.html': 'text/html'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def json_response(self, value, code=200):
        raw = json.dumps(value).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        if self.path.split('?')[0] == '/health':
            return self.json_response({'app': APP, 'root': str(ROOT), 'apiVersion': 1})
        if self.path.split('?')[0] in ('/settings', '/motions'):
            f = ROOT / (self.path.split('?')[0][1:] + '.json')
            return self.json_response(json.loads(f.read_text(encoding='utf-8')) if f.exists() else {})
        return super().do_GET()

    def do_POST(self):
        if self.path.split('?')[0] in ('/settings', '/motions'):   # persistent UI settings / saved speech-pose motions
            name = self.path.split('?')[0][1:]
            value = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            if not isinstance(value, dict): return self.json_response({'error': 'expected object'}, 400)
            tmp = ROOT / (name + '.json.tmp'); tmp.write_text(json.dumps(value, indent=1), encoding='utf-8')
            tmp.replace(ROOT / (name + '.json'))   # atomic: a crash never leaves a half-written file
            return self.json_response({'ok': True})
        if self.path.split('?')[0] != '/snapshot':
            return self.json_response({'error': 'unknown'}, 404)
        n = int(self.headers.get('Content-Length', 0))
        value = json.loads(self.rfile.read(n))
        png = base64.b64decode(value.pop('image').split(',', 1)[1])
        if not png.startswith(b'\x89PNG'):
            return self.json_response({'error': 'expected png'}, 400)
        (ROOT / 'current_view.png').write_bytes(png)
        (ROOT / 'current_view.json').write_text(json.dumps(value, indent=1), encoding='utf-8')
        return self.json_response({'ok': True})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--port', type=int, default=8842)
    port = p.parse_args().port
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
