"""Compare full-body temporal continuity, not merely contact positions."""
import json,pickle
import numpy as np
from scipy.spatial.transform import Rotation as R
from clean_slow_contacts import Geometry,P,OUT,sample,interpolate

def metrics(g,frames,fps):
 p,r,b=sample(g,frames)
 v=np.diff(p,axis=0)*fps
 w=R.from_matrix((r[1:]@r[:-1].transpose(0,1,3,2)).reshape(-1,3,3)).as_rotvec().reshape(-1,15,3)*fps
 return {name:dict(speed_m_s=float(np.linalg.norm(v[:,i],axis=1).max()),
  angular_deg_s=float(np.rad2deg(np.linalg.norm(w[:,i],axis=1).max())),
  peak_rotation_source_frame=float(np.argmax(np.linalg.norm(w[:,i],axis=1))*30/fps),
  acceleration_m_s2=float(np.linalg.norm(np.diff(v[:,i],axis=0)*fps,axis=1).max()),
  angular_accel_deg_s2=float(np.rad2deg(np.linalg.norm(np.diff(w[:,i],axis=0)*fps,axis=1).max()))) for i,name in enumerate(g.names)}

if __name__=='__main__':
 g=Geometry();report={}
 for name in ['crawl','crawl_idle']:
  m=pickle.loads((OUT/'candidates'/f'{name}.pkl').read_bytes());f=m['frames']
  o=pickle.loads((OUT/'before'/f'{name}.pkl').read_bytes())['frames']
  if len(o)!=len(f):o=interpolate(g,o,round((len(f)-1)/(len(o)-1)))
  report[name]=dict(original=metrics(g,o,m['fps']),candidate=metrics(g,f,m['fps']))
  for b in ['pelvis','torso','right_thigh','right_shin','right_foot','left_thigh','left_shin','left_foot']:
   print(name,b, {k:round(v,2) for k,v in report[name]['original'][b].items()}, {k:round(v,2) for k,v in report[name]['candidate'][b].items()},flush=True)
 (OUT/'temporal-audit.json').write_text(json.dumps(report,indent=2))
