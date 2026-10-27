"""Small independent loopback service. No Unreal, physics or inference workers."""
import argparse, base64, json, threading, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parent
LOCK=threading.Lock()
class Handler(SimpleHTTPRequestHandler):
    extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.js':'text/javascript'}
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
    def log_message(self,*a): pass
    def end_headers(self):
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');super().end_headers()
    def reply(self,value,status=200):
        raw=json.dumps(value,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        route=urlparse(self.path).path
        if route=='/health':return self.reply(dict(app='throw-lab',root=str(ROOT),apiVersion=1))
        if route=='/state':
            with LOCK:
                p=ROOT/'state.json';return self.reply(json.loads(p.read_text(encoding='utf-8')) if p.exists() else {})
        return super().do_GET()
    def do_POST(self):
        if self.headers.get('Origin','') not in ('',f'http://{self.headers.get("Host")}'):return self.reply({'error':'Local app only'},403)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<8000000:raise ValueError('Invalid payload size')
            data=json.loads(self.rfile.read(size));route=urlparse(self.path).path
            with LOCK:
                if route=='/state':
                    p=ROOT/'state.tmp';p.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8');p.replace(ROOT/'state.json');return self.reply({'saved':True})
                if route=='/snapshot':
                    folder=ROOT/'snapshots';folder.mkdir(exist_ok=True);name=time.strftime('%Y%m%d-%H%M%S')+f'-{time.time_ns()%1000000:06d}'
                    image=base64.b64decode(data.pop('image').split(',',1)[1],validate=True)
                    if not image.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Expected PNG')
                    (folder/(name+'.png')).write_bytes(image);(folder/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8');return self.reply({'name':name})
            return self.reply({'error':'Unknown route'},404)
        except Exception as exc:return self.reply({'error':str(exc)},400)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8893);args=parser.parse_args()
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
