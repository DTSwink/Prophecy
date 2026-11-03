"""Local pose authoring service. Never writes to a training package or pod."""
import base64, hashlib, json, pickle, re, threading, time
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry, ROOT, OUT as OLD
from repair_slow_arms import OUT as ARMS

OUT=ROOT/'Saved/MimicKitSlowLoco/pose-editor';OUT.mkdir(exist_ok=True,parents=True)
G=Geometry();LOCK=threading.Lock()
BASE=pickle.loads((ARMS/'sitting.pkl').read_bytes())['frames'][20].astype(float)
ORIGINAL=pickle.loads((OLD/'before/motions/sitting.pkl').read_bytes())['frames'][20].astype(float)
BASE_SHA=hashlib.sha256((ARMS/'sitting.pkl').read_bytes()).hexdigest()
LAST_REQUEST=time.monotonic()
def frame(value):
    a=np.asarray(value,dtype=float)
    if a.shape!=(40,) or not np.isfinite(a).all() or np.abs(a).max()>1000:raise ValueError('Expected 40 finite pose coordinates')
    return a
def audit(f):
    with LOCK:
        p,r=G.fk(f);G.set_pose(p,r)
        gaps=[G.distance(a,b) for a,b in G.pairs];floor=G.floors();limits=G.limits(f)
        collisions=[dict(a=G.gs[a]['body'],b=G.gs[b]['body'],depth_cm=round(-v*100,3)) for (a,b),v in zip(G.pairs,gaps) if v<-.001]
    return dict(collisions=sorted(collisions,key=lambda x:-x['depth_cm']),floor_min_cm=float(floor.min()*100),
        joint_limits=[k for k,v in limits.items() if v],positions=p.tolist(),quaternions=R.from_matrix(r).as_quat().tolist())
def model():
    joints=[]
    for i in range(1,15):
        j=G.k.get_joint(i);m=next(x for x in G.meta['joints'] if x['body']==G.names[i])
        joints.append(dict(body=i,index=6+j.dof_idx,size=j.get_dof_dim(),axis=j.axis.numpy().tolist() if j.get_dof_dim()==1 else None,limits=m))
    return dict(names=G.names,parents=G.parents.tolist(),local_p=G.lp.tolist(),local_q=R.from_matrix(G.lr).as_quat().tolist(),
        joints=joints,geometry=[dict(**g,body_id=int(G.gb[i]),local_p=G.gp[i].tolist(),local_q=R.from_matrix(G.gr[i]).as_quat().tolist()) for i,g in enumerate(G.gs)],
        base=BASE.tolist(),original=ORIGINAL.tolist(),base_sha256=BASE_SHA,source_frame=20,clip='sitting',
        saved=json.loads((OUT/'current.json').read_text()) if (OUT/'current.json').exists() else None,
        reference_fk=audit(BASE))
class Handler(SimpleHTTPRequestHandler):
    def handle_one_request(self):
        global LAST_REQUEST
        LAST_REQUEST=time.monotonic()
        return super().handle_one_request()
    def log_message(self,*args):pass
    def json(self,data,status=200):
        body=json.dumps(data,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.path.split('?')[0]=='/api/model':return self.json(model())
        if self.path=='/':self.path='/Labs/RoboticMotionAE/pose_editor/index.html'
        return super().do_GET()
    def do_POST(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<8_000_000:raise ValueError('Invalid request size')
            data=json.loads(self.rfile.read(length));f=frame(data['frame']);report=audit(f)
            if self.path=='/api/validate':return self.json(report)
            if self.path!='/api/save':return self.json(dict(error='Unknown endpoint'),404)
            if data.get('base_sha256')!=BASE_SHA:raise ValueError('Pose base changed; reload before saving')
            stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
            receipt=dict(schema=1,clip='sitting',source_frame=20,saved_utc=datetime.now(timezone.utc).isoformat(),
                base_sha256=BASE_SHA,frame=f.tolist(),base_frame=BASE.tolist(),
                changed_coordinates=np.flatnonzero(np.abs(f-BASE)>1e-8).tolist(),
                validation=report,training_applied=False)
            encoded=data.get('screenshot','')
            if encoded.startswith('data:image/png;base64,'):
                blob=base64.b64decode(encoded.split(',',1)[1],validate=True)
                if not blob.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Invalid PNG')
                (OUT/('pose_'+stamp+'.png')).write_bytes(blob)
                receipt['preview']='Saved/MimicKitSlowLoco/pose-editor/pose_'+stamp+'.png'
            version=OUT/('pose_'+stamp+'.json');version.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
            (OUT/'current.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
            return self.json(dict(saved=True,path=version.relative_to(ROOT).as_posix(),current='Saved/MimicKitSlowLoco/pose-editor/current.json',validation=report))
        except Exception as e:self.json(dict(error=str(e)),400)
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--idle-timeout',type=float,default=1800,
        help='Exit after this many seconds without requests (default: 30 minutes).')
    args=parser.parse_args()
    if args.idle_timeout<=0:parser.error('--idle-timeout must be positive')
    server=ThreadingHTTPServer(('127.0.0.1',8871),partial(Handler,directory=str(ROOT)))
    server.timeout=min(5,args.idle_timeout)
    server.daemon_threads=True
    print('Pose editor http://127.0.0.1:8871/ ; training untouched',flush=True)
    try:
        while time.monotonic()-LAST_REQUEST<args.idle_timeout:
            server.handle_request()
    finally:
        server.server_close()
        print('Pose editor idle; exiting. Saved poses are retained.',flush=True)
