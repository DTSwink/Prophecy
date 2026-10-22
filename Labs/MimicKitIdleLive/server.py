"""Request-driven local simulator: no worker loop, no computation while paused."""
import json,time,threading,mimetypes,traceback
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from simulation import Simulation,ROOT,OUT
HERE=Path(__file__).parent
PORT=8850

class App:
    def __init__(self):
        self.sim=Simulation();self.paused=True;self.last_step=0.;self.lock=threading.Lock()
    def state(self):return dict(**self.sim.state(),paused=self.paused)
    def command(self,cmd,payload):
        with self.lock:
            if cmd=='play':self.paused=False
            elif cmd=='pause':self.paused=True
            elif cmd=='reset':self.sim.reset(payload.get('drawn',False))
            elif cmd=='impulse':self.sim.kick(payload['body'],payload['direction'],payload['strength'])
            elif cmd=='step':
                if not self.paused:self.sim.tick()
            else:raise ValueError('Unknown command')
            return self.state()

class Handler(BaseHTTPRequestHandler):
    def send(self,content,kind='application/json',status=200):
        if not isinstance(content,bytes):content=json.dumps(content,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content)
    def do_GET(self):
        path=self.path.split('?')[0]
        if path=='/api/state':
            with app.lock:self.send(app.state())
            return
        if path=='/api/info':self.send(app.sim.geometry());return
        routes={'/':HERE/'index.html','/app.js':HERE/'app.js','/three.module.js':ROOT/'Labs/MimicKitUEFN/vendor/three.module.js','/OrbitControls.js':ROOT/'Labs/MimicKitUEFN/vendor/OrbitControls.js'}
        f=routes.get(path)
        if f is None or not f.is_file():self.send_error(404);return
        self.send(f.read_bytes(),'text/javascript' if f.suffix=='.js' else 'text/html; charset=utf-8')
    def do_POST(self):
        origin=self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'):
            self.send({'error':'Invalid origin'},status=403);return
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':self.send_error(415);return
        n=int(self.headers.get('Content-Length','0'))
        if not 0<n<=4096:self.send_error(400);return
        try:
            payload=json.loads(self.rfile.read(n));self.send(app.command(self.path.removeprefix('/api/'),payload))
        except (ValueError,KeyError,TypeError) as e:self.send({'error':str(e)},status=400)
        except Exception as e:
            app.paused=True;traceback.print_exc();self.send({'error':str(e)},status=500)
    def log_message(self,*args):pass

if __name__=='__main__':
    app=App();(OUT/'server-ready.json').write_text(json.dumps(dict(port=PORT,paused=True,checkpoint=app.sim.geometry()['checkpoint'])))
    print(f'Ready http://127.0.0.1:{PORT} — paused',flush=True)
    ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
