"""Read-only feasibility audit of the exact packaged recovery references."""
import sys,json,pickle,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Labs/MimicKitUEFN'),str(ROOT/'Labs/RoboticCrawlAE')]
import prepare as ae
from fit_motion_limits import sampled_coordinates,violation
import numpy as np,torch
from scipy.spatial.transform import Rotation as R
torch.set_num_threads(1)
asset=ROOT/'Saved/MimicKitEquipment/package/assets/uefn'
meta=json.loads((asset/'limits.json').read_text())
model=ae.rt.MJCFCharModel('cpu');model.load(str(asset/'humanoid_uefn.xml'))
names=model.get_body_names();results=[]
for clip in ('front','back'):
 for variant in ('robotic','reset_floor_ik'):
  path=ROOT/f'Saved/MimicKitEquipment/package/motions/recovery/getUp_{clip}_quick_{variant}.pkl'
  data=pickle.loads(path.read_bytes());frames=data['frames'];p,q=ae.fk(model,frames)
  heights={}
  for geom in meta['geometry']:
   name=geom['body'];i=names.index(name);frame=meta['body_frames'][name]
   rest=R.from_quat(frame['quaternion']);localp=rest.inv().apply(np.asarray(geom['position'])-frame['position'])
   localr=rest.inv()*R.from_quat(geom['quaternion']);rot=R.from_quat(q[:,i])*localr
   centre=p[:,i]+R.from_quat(q[:,i]).apply(localp);size=geom['size']
   if geom['type']=='box':extent=sum(abs(rot.apply(np.eye(3)[j])[:,2])*size[j] for j in range(3))
   elif geom['type']=='capsule':extent=size[0]+size[1]*abs(rot.apply([0,0,1])[:,2])
   else:extent=size[0]
   bottom=centre[:,2]-extent
   heights[name]=np.minimum(heights.get(name,np.full(len(frames),np.inf)),bottom)
  limits=[]
  for joint in meta['joints']:
   values,_=sampled_coordinates(model,joint,frames,1);bad=violation(values,joint)
   modes=joint['modes'];lim=joint['limits_rad']
   twist=np.rad2deg(np.maximum(0,np.abs(values[:,0])-(lim[0] if modes[0]==1 else 0)))
   limits.append(dict(body=joint['body'],bad_frames=np.flatnonzero(bad).tolist(),twist_excess_degrees=twist.tolist(),
    swing_ellipse_radius=(np.sqrt((values[:,1]/np.sin(lim[1]/2))**2+(values[:,2]/np.sin(lim[2]/2))**2).tolist() if modes[1]==modes[2]==1 else None)))
  results.append(dict(clip=clip,variant=variant,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),frames=len(frames),fps=data['fps'],
   minimum_height_by_body={k:v.tolist() for k,v in heights.items()},limits=limits))
out=ROOT/'Saved/MimicKitEquipment/getup-start-audit/targets.json';out.write_text(json.dumps(results,indent=2))
for r in results:
 print(r['clip'],r['variant'])
 print('penetration cm',[(k,round(-min(v)*100,2)) for k,v in r['minimum_height_by_body'].items() if min(v)<-.001])
 print('limits',[(j['body'],len(j['bad_frames']),round(max(j['twist_excess_degrees']),2),round(max(j['swing_ellipse_radius']),2) if j['swing_ellipse_radius'] else None) for j in r['limits'] if j['bad_frames']])
