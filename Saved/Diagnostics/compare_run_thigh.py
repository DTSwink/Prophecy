import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics/RunHandThigh')
def d(v,a,b):
 v=np.array(v);a=np.array(a);b=np.array(b);x=b-a
 return float(np.linalg.norm(v-a-np.clip(np.dot(v-a,x)/max(np.dot(x,x),1e-12),0,1)*x))
report={}
for tag in ['baseline','meshes','feedback','sheathed','zero_gaze']:
 path=p/(tag+'.json')
 if not path.exists():continue
 data=json.loads(path.read_text());rows=data['rows'];result={}
 for side in ['l','r']:
  for phase in ['future','presented','PhysicalMesh','KinematicMesh','NNKinematicMesh']:
   candidates=[]
   for r in rows:
    pose=r.get(phase) or r.get('meshes',{}).get(phase,{}).get('bones',{})
    if not pose or 'hand_l' not in pose:continue
    for bone in ['hand_l','index_03_l','middle_03_l','ring_03_l','pinky_03_l']:
     if bone not in pose:continue
     candidates.append((d(pose[bone]['p'],pose['thigh_'+side]['p'],pose['calf_'+side]['p']),r['tick'],bone))
   if candidates:result[phase+'_thigh_'+side]=min(candidates)
 report[tag]=dict(error=data['error'],frames=len(rows),minima=result,meshes=list(rows[-1].get('meshes',{})),attacks=sorted(set(r['attack'] for r in rows)))
(p/'comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
