"""Rating page for the French-accent tries (local only, 127.0.0.1:8843).
python Tools/Speech/accent_rate_server.py   ->  http://127.0.0.1:8843/accent/rate.html
Serves Saved/Speech (audio) and keeps the ratings in Saved/Speech/accent/ratings.json (GET/POST /ratings)."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[2] / 'Saved' / 'Speech'
OUT = ROOT / 'accent' / 'ratings.json'

class H(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.mp3': 'audio/mpeg', '.json': 'application/json', '.html': 'text/html', '.js': 'text/javascript'}
    def __init__(self, *a, **k): super().__init__(*a, directory=str(ROOT), **k)
    def log_message(self, *a): pass
    def end_headers(self): self.send_header('Cache-Control', 'no-cache'); super().end_headers()
    def js(self, v, code=200):
        raw = json.dumps(v).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        if self.path.split('?')[0] == '/ratings': return self.js(json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {})
        return super().do_GET()
    def do_POST(self):
        if self.path.split('?')[0] != '/ratings': return self.js({'error': 'unknown'}, 404)
        v = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        if not isinstance(v, dict): return self.js({'error': 'expected object'}, 400)
        tmp = OUT.with_suffix('.json.tmp'); tmp.write_text(json.dumps(v, indent=1, ensure_ascii=False), encoding='utf-8'); tmp.replace(OUT)
        return self.js({'ok': True})

if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8843), H).serve_forever()
