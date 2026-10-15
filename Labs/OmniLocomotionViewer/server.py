"""Read-only localhost viewer. Serves only viewer assets and captured motions."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import json,mimetypes
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  path=self.path.split('?')[0]
  routes={'/':HERE/'index.html','/app.js':HERE/'app.js','/data.json':HERE/'data.json','/shared/renderer.js':ROOT/'Labs/SwordHolsterLab/renderer.js','/shared/recovery.js':ROOT/'Labs/SwordHolsterLab/recovery.js'}
  f=routes.get(path)
  if not f or not f.is_file():self.send_error(404);return
  b=f.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(f.name)[0] or 'application/octet-stream');self.send_header('Cache-Control','no-cache');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def log_message(self,*args):pass
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8841),Handler).serve_forever()
