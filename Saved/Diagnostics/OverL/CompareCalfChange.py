import sys,pathlib,json,numpy as np
from scipy.spatial.transform import Rotation
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from CompareRecoveryLegs import load

def compare(a,b):
 pa,qa,ma=load(a);pb,qb,mb=load(b)
 keys=['lower_input','lower_delta','walk_delta','published_lower','previous_lower','upper_input','upper_delta']
 diff={}
 for key in keys:
  ds=[np.max(np.abs(np.array(qa[t][key])-qb[t][key])) for t in qa.keys() & qb.keys() if key in qa[t] and key in qb[t]]
  if ds:diff[key]=float(max(ds))
 bones={}
 for bone in ma[next(iter(ma))]['bones']:
  pos=[];rot=[]
  for t in ma.keys() & mb.keys():
   for kind in ['future','target','visible']:
    x,y=ma[t]['bones'][bone][kind],mb[t]['bones'][bone][kind]
    pos.append(np.linalg.norm(np.array(x['p'])-y['p']))
    rot.append(np.degrees((Rotation.from_quat(x['q'])*Rotation.from_quat(y['q']).inv()).magnitude()))
  bones[bone]={'maximum_position_difference_cm':float(max(pos)),'maximum_rotation_difference_deg':float(max(rot))}
 report={'baseline':pa.name,'candidate':pb.name,'max_pipeline_difference':diff,'bones':bones}
 (pb/'calf-change-comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':compare(*sys.argv[1:3])
