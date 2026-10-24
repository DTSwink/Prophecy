"""Bodyflip-only loopback server. No editor, training, or other lab routes."""
import argparse, base64, json, threading, time
from collections import OrderedDict
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from run_bank import read_run
ROOT=Path(__file__).resolve().parent
LOCK=threading.Lock()
NN_LOCK=threading.Lock()
RUN_CACHE=OrderedDict()
class Handler(SimpleHTTPRequestHandler):
    extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.mjs':'text/javascript','.js':'text/javascript','.wasm':'application/wasm','.svg':'image/svg+xml'}
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
    def log_message(self,*a): pass
    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        super().end_headers()
    def reply(self,value,status=200):
        raw=json.dumps(value,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/health': return self.reply({'app':'bodyflip-lab','root':str(ROOT),'apiVersion':4})
        if path=='/state':
            with LOCK:
                p=ROOT/'state.json';return self.reply(json.loads(p.read_text(encoding='utf-8')) if p.exists() else {})
        return super().do_GET()
    def do_POST(self):
        origin=self.headers.get('Origin','')
        if origin and origin!=f'http://{self.headers.get("Host")}': return self.reply({'error':'Local app only'},403)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<=0 or size>8000000: raise ValueError('Invalid payload size')
            data=json.loads(self.rfile.read(size));path=urlparse(self.path).path
            if path=='/run':
                duration=float(data.get('duration',1));phase=float(data.get('phase',0));drawn=bool(data.get('drawn',False))
                if not .1<=duration<=5 or not 0<=phase<=1: raise ValueError('Invalid run controls')
                gait=data.get('gait','run')
                if gait not in ('run','walk'): raise ValueError('Unknown gait')
                key=(gait,duration,phase,drawn)
                with NN_LOCK:
                    result=RUN_CACHE.get(key)
                    if result is None:
                        result=read_run(gait,duration,phase,drawn)
                    RUN_CACHE[key]=result;RUN_CACHE.move_to_end(key)
                    while len(RUN_CACHE)>4:RUN_CACHE.popitem(last=False)
                return self.reply(result)
            with LOCK:
                if path=='/state':
                    raw=json.dumps(data,indent=2,allow_nan=False);p=ROOT/'state.tmp';p.write_text(raw,encoding='utf-8');p.replace(ROOT/'state.json');return self.reply({'saved':True})
                if path=='/snapshot':
                    folder=ROOT/'snapshots';folder.mkdir(exist_ok=True);name=time.strftime('%Y%m%d-%H%M%S')+f'-{time.time_ns()%1000000:06d}'
                    image=base64.b64decode(data.pop('image').split(',',1)[1],validate=True)
                    if not image.startswith(b'\x89PNG\r\n\x1a\n'): raise ValueError('Expected PNG')
                    (folder/(name+'.png')).write_bytes(image);(folder/(name+'.json')).write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8');return self.reply({'name':name})
            self.reply({'error':'Unknown route'},404)
        except Exception as e: self.reply({'error':str(e)},400)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8876);a=p.parse_args()
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
