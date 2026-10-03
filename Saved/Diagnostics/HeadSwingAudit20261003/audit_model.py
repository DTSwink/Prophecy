import sys,json,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
import torch
torch.set_num_threads(2)
root=Path(__file__).resolve().parents[3];p=Path(__file__).parent
sys.path.insert(0,str(Path('C:/Users/singerie/Documents/Cursor/stepper')))
from training.ik import train_upper_pose_controller_pelvis as ctl
meta=json.loads((root/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
cp=torch.load(meta['checkpoint_path'],map_location='cpu',weights_only=False)
model=ctl.UpperCachedLowerAgent();model.load_state_dict(cp['model']);model.eval()
def clean_rot(v):
 x=np.array(v[:3]);x/=np.linalg.norm(x);y=np.array(v[3:]);y-=x*(x@y);y/=np.linalg.norm(y)
 return R.from_matrix(np.array([x,y,np.cross(x,y)]).T)
parents=dict(zip(meta['body_names'],meta['parents_body']))
mirror=np.diag([1,-1,1]);reports={}
for file in p.glob('*-inputs.jsonl'):
 name=file.name.removesuffix('-inputs.jsonl');poses=p/(name+'.json')
 if not poses.exists():continue
 rows={r['tick']:r for r in json.loads(poses.read_text())['rows']}
 trace=[r for r in map(json.loads,file.read_text().splitlines()) if r['actor']=='BP_ProphecyManualPoseAgent_C_0' and r['upper_inference']]
 x=np.array([r['upper_input'] for r in trace],np.float32)
 with torch.inference_mode():y=model(torch.from_numpy(x)).numpy()
 delta=np.array([r['upper_delta'] for r in trace]);records=[]
 for z,out in zip(trace,y):
  t=min(rows,key=lambda i:abs(rows[i]['time']-z['time']));r=rows[t];errors=[]
  if z['attack']:continue
  vals=np.array(z['upper_input'][90:180],np.float32)+np.array(z['upper_delta'],np.float32)
  for i,b in enumerate(meta['core_bones'][:8]):
   parent=meta['body_names'][parents[b]]
   expected=R.from_matrix(mirror@clean_rot(vals[i*6:i*6+6]).as_matrix()@mirror)
   actual=R.from_quat(r['bones'][parent]['future']['q']).inv()*R.from_quat(r['bones'][b]['future']['q'])
   errors.append(float(np.degrees((expected.inv()*actual).magnitude())))
  records.append(dict(tick=t,core_error_deg=max(errors),gaze=z['upper_input'][-2:],walk_weight=z['walk_weight']))
 metrics=[]
 for t,r in rows.items():
  if t-1 not in rows:continue
  old=rows[t-1];v={'tick':t}
  for kind in ['future','presented']:
   def local(row,b,parent):
    q=R.from_quat(row['bones'][parent][kind]['q']);s=row['bones'][b][kind]
    return q.inv().apply(np.array(s['p'])-row['bones'][parent][kind]['p']),q.inv()*R.from_quat(s['q'])
   p0,q0=local(old,'head','pelvis');p1,q1=local(r,'head','pelvis')
   _,h0=local(old,'head','neck_02');_,h1=local(r,'head','neck_02')
   v[kind+'_head_displacement_cm']=float(np.linalg.norm(p1-p0))
   v[kind+'_head_local_deg']=float(np.degrees((h0.inv()*h1).magnitude()))
   v[kind+'_head_pelvis_deg']=float(np.degrees((q0.inv()*q1).magnitude()))
  metrics.append(v)
 reports[name]=dict(torch_unreal_max_delta_error=float(np.max(np.abs(y-delta))),core_parity=records,metrics=metrics,
  attack_boundaries=[(t,r['attack']) for t,r in rows.items() if t-1 in rows and (r['attack']=='None')!=(rows[t-1]['attack']=='None')])
 report=reports[name];window=[r for r in metrics if 215<=r['tick']<=285]
 print(name,'torch parity',report['torch_unreal_max_delta_error'],'head peak',max(window,key=lambda r:r['presented_head_local_deg']),flush=True)
identity=dict(path=meta['checkpoint_path'],sha256=hashlib.sha256(Path(meta['checkpoint_path']).read_bytes()).hexdigest(),step=cp.get('step'),metadata=cp.get('metadata'),schema=cp.get('schema'))
(p/'checkpoint.json').write_text(json.dumps(identity,indent=2,default=str))
(p/'model-audit.json').write_text(json.dumps(reports,indent=2))
