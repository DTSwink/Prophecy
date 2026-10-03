import json,numpy as np
from pathlib import Path
base=Path(__file__).parent/'Diagnostics/TurnParity'
trace=[json.loads(l) for l in (base/'current_inputs.jsonl').read_text().splitlines()];trace=[r for r in trace if r['actor']=='BP_ProphecyManualPoseAgent_C_1'];original=np.array([r['roots'] for r in trace])
reference=np.load(base/'viewer_holding_sword_npz.npz');seed=np.array([[1,0,0],[0,0,-1],[0,1,0]])
def rot6(a):
 x=a[...,0:3];x=x/np.linalg.norm(x,axis=-1,keepdims=True);y=a[...,3:6];y=y-(y*x).sum(-1,keepdims=True)*x;y=y/np.linalg.norm(y,axis=-1,keepdims=True);return np.stack([x,y,np.cross(x,y)],-2)
def heading(y):
 a=np.tile(np.eye(3),(len(y),1,1));a[:,0,0]=np.cos(y);a[:,0,2]=-np.sin(y);a[:,2,0]=np.sin(y);a[:,2,2]=np.cos(y);return a
def yaw(bone,q):
 ref=reference['rotations'][0,list(reference['bones']).index(bone)];axis=np.array([0.,0.,1.])@ref.T
 f=axis@q;return -np.unwrap(np.arctan2(f[:,0],f[:,2]))*180/np.pi
report={}
for path in sorted(base.glob('coupled_*.npz')):
 v=np.load(path);l=v['lower'];u=v['upper'];roots=v['roots'] if 'roots' in v else original[:len(l)];h=heading(roots[:,11]);world={'pelvis':rot6(l[:,3:9])@seed@h}
 for i,b in enumerate(['spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head']):world[b]=rot6(u[:,i*6:i*6+6])@world['pelvis' if i==0 else ['spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head'][i-1]]
 # Stop before the oracle windows anticipate the NEXT turn at 10.0167 s.
 t=v['times'];mask=(t>=7.8)&(t<9.65);rw=-roots[:,11]*180/np.pi
 r={'turn':{},'feet':{}}
 for bone in ['pelvis','spine_05','head']:
  y=yaw(bone,world[bone]);a=y[mask];r['turn'][bone]={'peak':float(a.max()),'settled':float(a[-1]),'overshoot_settled_deg':float(a.max()-a[-1]),'overshoot_root_deg':float(a.max()-rw[mask].max())}
  if bone=='head':print(path.stem,'head overshoot',r['turn'][bone])
 for p,bone in [(9,'foot_l'),(25,'foot_r')]:
  pts=(l[:,p:p+3]@seed)[:,None,:]@h;pts=pts[:,0,:];speed=np.linalg.norm(np.diff(pts,axis=0)[:,[0,2]],axis=1)*30
  r['feet'][bone]={'distance_cm':float(np.linalg.norm(np.diff(pts[mask],axis=0)[:,[0,2]],axis=1).sum()*100),'moving_frames_over_5cm_s':int(np.count_nonzero(speed[mask[1:]]>.05)),'max_height_cm':float(pts[mask,1].max()*100)}
 print('feet',r['feet']);report[path.stem]=r
for path in base.glob('viewer_*.npz'):
 v=np.load(path);r={}
 for bone in ['pelvis','spine_05','head']:
  y=yaw(bone,v['rotations'][:,list(v['bones']).index(bone)]);r[bone]={'peak':float(y.max()),'settled':float(y[-1]),'overshoot_settled_deg':float(y.max()-y[-1])}
 print(path.stem,r);report[path.stem]=r
(base/'experiment_summary.json').write_text(json.dumps(report,indent=2))
