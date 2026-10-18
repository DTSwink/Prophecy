"""Local reach laboratory; isolated native kernel, explicit saves, no Unreal writes."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import argparse,ctypes,json,math,mimetypes,time,uuid,threading,base64,hashlib,re,os
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
DATA=json.loads((HERE/'data.json').read_text());N=26*7
DLL=ctypes.CDLL(os.environ.get('REACH_KERNEL_DLL',str(HERE/'bin/reach.dll')));D=ctypes.c_double;F=ctypes.c_float
DLL.reach_step.argtypes=[ctypes.POINTER(D),ctypes.POINTER(D),ctypes.POINTER(F),ctypes.c_int,ctypes.POINTER(D),ctypes.POINTER(D)]
DLL.reach_step.restype=ctypes.c_int
DLL.reach_step_blend.argtypes=DLL.reach_step.argtypes+[D]
DLL.reach_step_blend.restype=ctypes.c_int
BASE=(D*N)(*[v for p in DATA['base'] for v in p]);LOCK=threading.RLock()
SESSION={};LIVE=None;LIVE_IMAGE=None
MOTIONS={}
def numbers(a,n,bound=1e6):
 if not isinstance(a,list) or len(a)!=n or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or abs(v)>bound for v in a):raise ValueError('Invalid numeric vector')
 return a
def solve(req):
 targets=numbers(req['targets'],6,1000);state=numbers(req.get('state',[0]*20),20);speeds=numbers(req.get('speeds',[120,120]),2,1000)
 if min(speeds)<0:raise ValueError('Negative speed')
 blend=numbers([req.get('elbowDownBlend',1)],1,1)[0]
 if blend<0:raise ValueError('Elbow down blend must be in [0,1]')
 mode=req['mode'];steps=req.get('steps',1)
 if type(mode)!=int or not 0<=mode<=3 or type(steps)!=int or not 1<=steps<=8:raise ValueError('Invalid mode/steps')
 s=(D*20)(*state);t=(D*6)(*targets);v=(F*2)(*speeds);out=(D*N)();start=time.perf_counter()
 base=BASE
 if 'basePose' in req:
  pose=req['basePose']
  if not isinstance(pose,list) or len(pose)!=26:raise ValueError('Invalid base pose')
  base=(D*N)(*[v for bone in pose for v in numbers(bone,7)])
 poses=[]
 for _ in range(steps):
  if not DLL.reach_step_blend(base,t,v,mode,s,out,blend):raise ValueError('Solver rejected input')
  poses.append([list(out[i*7:(i+1)*7]) for i in range(26)])
 return dict(pose=poses[-1],poses=poses,state=list(s),solveMs=(time.perf_counter()-start)*1000,steps=steps)
def atomic(path,data):
 raw=json.dumps(data,allow_nan=False,indent=2).encode();tmp=path.with_suffix('.tmp')
 with LOCK:tmp.write_bytes(raw);tmp.replace(path)
def read_json(path,default=None):
 return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def motion_file(identifier):
 if not isinstance(identifier,str) or not re.fullmatch(r'[a-f0-9]{64}',identifier):raise ValueError('Invalid motion reference')
 return STORE/'motions'/(identifier+'.json')

def retain_motion(motion):
 if not isinstance(motion,dict) or not isinstance(motion.get('frames'),list):raise ValueError('Invalid recorded motion')
 # Old desktop clients still send full recordings. Equality avoids serializing
 # their unchanged recording again; new clients upload it only once.
 with LOCK:
  for identifier,cached in MOTIONS.items():
   if cached==motion:return identifier
  raw=json.dumps(motion,allow_nan=False,separators=(',',':')).encode()
  identifier=hashlib.sha256(raw).hexdigest();dest=motion_file(identifier)
  dest.parent.mkdir(exist_ok=True)
  if not dest.exists():
   tmp=dest.with_suffix('.tmp');tmp.write_bytes(raw);tmp.replace(dest)
  MOTIONS[identifier]=motion
  return identifier

def compact_state(state):
 result=dict(state)
 if 'motion' in result:
  motion=result.pop('motion');result['motionRef']={'id':retain_motion(motion),'startTick':motion['startTick']}
 elif 'motionRef' in result and not motion_file(result['motionRef']['id']).is_file():raise ValueError('Recorded motion is missing')
 return result

def expand_state(state):
 result=dict(state);reference=result.pop('motionRef',None)
 if reference:
  identifier=reference['id'];dest=motion_file(identifier)
  if not dest.is_file():raise ValueError('Recorded motion is missing')
  if identifier not in MOTIONS:MOTIONS[identifier]=read_json(dest)
  result['motion']=MOTIONS[identifier]
 return result

def image_bytes(value):
 raw=base64.b64decode(value.split(',',1)[-1],validate=True)
 if not raw.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Expected PNG')
 return raw

class Handler(BaseHTTPRequestHandler):
 def is_desktop(self):
  token=self.headers.get('X-Desktop-Session');client=self.headers.get('X-Client-Id')
  if not token or token!=SESSION.get('token') or not client:return False
  with LOCK:
   if not SESSION.get('clientId'):
    SESSION['clientId']=client;atomic(STORE/'desktop_session.json',SESSION)
   return client==SESSION.get('clientId')
 def log_message(self,*args):pass
 def send(self,data,status=200,kind='application/json'):
  raw=data if isinstance(data,bytes) else json.dumps(data,allow_nan=False).encode()
  if kind.startswith('text/') or kind in ['application/javascript','application/json']:kind+='; charset=utf-8'
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  p=urlsplit(self.path).path
  if p in ['/reach','/reach/']:p='/'
  if p=='/health':return self.send(dict(app='reach-lab',root=str(HERE),sourceSha256=DATA['sourceSha256'],apiVersion=3))
  if p=='/reset-defaults':return self.send(read_json(HERE/'reset_defaults.json'))
  if p=='/session':return self.send(expand_state(read_json(STORE/'session.json',{})))
  if p.startswith('/motions/'):
   identifier=p.removeprefix('/motions/').removesuffix('.json')
   if not re.fullmatch(r'[a-f0-9]{64}',identifier):return self.send({'error':'Invalid motion reference'},400)
   dest=motion_file(identifier)
   if not dest.is_file():return self.send({'error':'Recorded motion missing'},404)
   return self.send(dest.read_bytes())
  if p=='/snapshots':return self.send(sorted([f.stem for f in (STORE/'snapshots').glob('*.json')],reverse=True))
  if p.startswith('/snapshots/'):
   name=p.removeprefix('/snapshots/')
   if not re.fullmatch(r'[A-Za-z0-9_-]+\.(json|png)',name):return self.send({'error':'Invalid snapshot'},400)
   f=STORE/'snapshots'/name
   if not f.is_file():return self.send({'error':'Snapshot missing'},404)
   return self.send(f.read_bytes(),kind='image/png' if f.suffix=='.png' else 'application/json')
  if p in ['/desktop-view','/desktop-view.png','/current-view.png']:
   with LOCK:
    if p=='/desktop-view':return self.send({'ok':LIVE is not None,**(LIVE or {})})
    sequence=parse_qs(urlsplit(self.path).query).get('sequence',[''])[0]
    if not LIVE or (sequence and sequence!=str(LIVE['sequence'])):return self.send({'error':'View changed; reread desktop-view'},409)
    return self.send(LIVE_IMAGE,kind='image/png')
  if p=='/state':return self.send(json.loads((STORE/'state.json').read_text()) if (STORE/'state.json').exists() else {})
  if p=='/current-view':return self.send(json.loads((STORE/'current_view.json').read_text()) if (STORE/'current_view.json').exists() else {})
  routes={**{('/' if n=='index.html' else '/'+n):HERE/n for n in ['index.html','app.js','workspace.js','reach-renderer.js','capture.js','capture-worker.js','style.css','data.json','phat.json','icon.svg','icon.ico','wrist.js','grab.js','fingers.json','coupled.js']},'/shared/renderer.js':ROOT/'Labs/SwordHolsterLab/renderer.js','/shared/recovery.js':ROOT/'Labs/SwordHolsterLab/recovery.js'}
  f=routes.get(p)
  if not f or not f.is_file():return self.send({'error':'Not found'},404)
  return self.send(f.read_bytes(),kind=mimetypes.guess_type(f.name)[0] or 'application/octet-stream')
 def do_POST(self):
  global SESSION,LIVE,LIVE_IMAGE
  try:
   origin=self.headers.get('Origin')
   if origin and origin not in [f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}']:return self.send({'error':'Origin mismatch'},403)
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=16*1024*1024:raise ValueError('Invalid request size')
   req=json.loads(self.rfile.read(size));p=urlsplit(self.path).path
   if not isinstance(req,dict):raise ValueError('Expected object')
   if p=='/step':return self.send(solve(req))
   if p=='/desktop-session':
    token=req.get('token','')
    if not isinstance(token,str) or len(token)<24:raise ValueError('Invalid desktop session')
    with LOCK:
     SESSION={'token':token,'clientId':None};LIVE=LIVE_IMAGE=None;atomic(STORE/'desktop_session.json',SESSION)
    return self.send({'ok':True})
   if not self.is_desktop():return self.send({'error':'Only the registered desktop may save or publish'},403)
   if p=='/motion':return self.send({'id':retain_motion(req)})
   if p=='/session':atomic(STORE/'session.json',compact_state(req));return self.send({'saved':True})
   if p=='/desktop-view':
    png=image_bytes(req.pop('image'));sequence=int(req['sequence'])
    req=compact_state(req);req['state']=compact_state(req['state'])
    with LOCK:
     if LIVE and sequence<=LIVE['sequence']:return self.send({'stale':True})
     req.update(clientId=SESSION['clientId'],receivedAt=time.time(),imageSha256=hashlib.sha256(png).hexdigest())
     LIVE,LIVE_IMAGE=req,png
     (STORE/'current_view.png').write_bytes(png);atomic(STORE/'current_view.json',req)
     atomic(STORE/'session.json',req['state'])
    return self.send({'ok':True})
   if p=='/state':atomic(STORE/'state.json',req);return self.send({'saved':True})
   if p=='/current-view':atomic(STORE/'current_view.json',req);return self.send({'saved':True})
   if p=='/snapshot':
    raw=image_bytes(req.pop('image'));req=expand_state(req)
    with LOCK:
     folder=STORE/'snapshots';folder.mkdir(exist_ok=True)
     number=max([int(f.stem.split('_')[-1]) for f in folder.glob('snapshot_*.json') if re.fullmatch(r'snapshot_\d+',f.stem)],default=0)+1
     name=f'snapshot_{number:04d}';req.update(capturedAt=time.time(),clientId=SESSION['clientId'])
     (folder/(name+'.png')).write_bytes(raw);atomic(folder/(name+'.json'),req)
    return self.send({'saved':name,'name':name,'path':str(folder/(name+'.json'))})
   return self.send({'error':'Not found'},404)
  except (ValueError,KeyError,TypeError) as e:return self.send({'error':str(e)},400)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8873);ap.add_argument('--state-dir',type=Path,default=HERE);a=ap.parse_args();STORE=a.state_dir;STORE.mkdir(parents=True,exist_ok=True)
 SESSION=read_json(STORE/'desktop_session.json',{})
 ThreadingHTTPServer.request_queue_size=64
 ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
