"""Foot IK-only loopback server. No editor, training, or other lab routes."""
import argparse, base64, json, os, threading, time
from collections import OrderedDict
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from run_bank import read_run
from nn_service import resume
ROOT=Path(__file__).resolve().parent
STATE_FILE=ROOT/'state.json'
LOCK=threading.Lock()
NN_LOCK=threading.Lock()
RUN_CACHE=OrderedDict()
STATE_CLIENTS=OrderedDict()
def save_changes(data):
    """Called under LOCK. Merge only edited fields; ignore delayed old requests."""
    client=data.get('client');sequence=data.get('sequence');changes=data.get('changes')
    if not isinstance(client,str) or not 1<=len(client)<=100 or type(sequence) is not int or sequence<1 or not isinstance(changes,dict):
        raise ValueError('Refresh Foot IK to update its save protocol; no saved settings were changed.')
    if sequence<=STATE_CLIENTS.get(client,0): return {'saved':True,'superseded':True}
    current=json.loads(STATE_FILE.read_text(encoding='utf-8')) if STATE_FILE.exists() else {'schema':'foot-ik-lab-v1'}
    for section,fields in changes.items():
        if section not in ('settings','camera','playback') or not isinstance(fields,dict): raise ValueError('Invalid saved state section')
        current.setdefault(section,{}).update(fields)
    raw=json.dumps(current,indent=2,allow_nan=False)
    STATE_FILE.parent.mkdir(parents=True,exist_ok=True)
    temporary=STATE_FILE.with_suffix('.tmp')
    with temporary.open('w',encoding='utf-8') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    temporary.replace(STATE_FILE)
    STATE_CLIENTS[client]=sequence;STATE_CLIENTS.move_to_end(client)
    while len(STATE_CLIENTS)>256: STATE_CLIENTS.popitem(last=False)
    return {'saved':True}
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
        if path=='/health': return self.reply({'app':'foot-ik-lab','root':str(ROOT),'apiVersion':7,'stateProtocol':2,'generationProtocol':1,'stateFile':str(STATE_FILE)})
        if path=='/state':
            with LOCK:
                p=STATE_FILE;return self.reply(json.loads(p.read_text(encoding='utf-8')) if p.exists() else {})
        return super().do_GET()
    def do_POST(self):
        origin=self.headers.get('Origin','')
        if origin and origin!=f'http://{self.headers.get("Host")}': return self.reply({'error':'Local app only'},403)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<=0 or size>8000000: raise ValueError('Invalid payload size')
            data=json.loads(self.rfile.read(size));path=urlparse(self.path).path
            if path=='/resume':
                return self.reply(resume(data))
            if path=='/run':
                duration=float(data.get('duration',1));phase=float(data.get('phase',0));drawn=False
                if not .1<=duration<=5 or not 0<=phase<=1: raise ValueError('Invalid run controls')
                gait=data.get('gait','run')
                if gait not in ('run','walk'): raise ValueError('Unknown gait')
                direction=data.get('direction','forward')
                if direction not in ('forward','backward','left','right'): raise ValueError('Unknown gait direction')
                if direction!='forward':
                    return self.reply(resume(dict(kind='direction',gait=gait,direction=direction,duration=duration,phase=phase,drawn=False)))
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
                    return self.reply(save_changes(data))
                if path=='/snapshot':
                    folder=ROOT/'snapshots';folder.mkdir(exist_ok=True);name=time.strftime('%Y%m%d-%H%M%S')+f'-{time.time_ns()%1000000:06d}'
                    image=base64.b64decode(data.pop('image').split(',',1)[1],validate=True)
                    if not image.startswith(b'\x89PNG\r\n\x1a\n'): raise ValueError('Expected PNG')
                    (folder/(name+'.png')).write_bytes(image);(folder/(name+'.json')).write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8');return self.reply({'name':name})
            self.reply({'error':'Unknown route'},404)
        except Exception as e: self.reply({'error':str(e)},400)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8878);p.add_argument('--state-file',type=Path);a=p.parse_args()
    if a.state_file: STATE_FILE=a.state_file.resolve()
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
