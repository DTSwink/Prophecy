import os
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import pathlib,json,numpy as np,torch
from scipy.spatial.transform import Rotation
from ReplayTemperedLeg import rot,clean
p=pathlib.Path(__file__).resolve().parents[2];d=p/'Saved/Diagnostics'
c=json.loads((p/'Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json').read_text())
torch.set_num_threads(1);torch.set_num_interop_threads(1)
cp=torch.load(c['checkpoint_path'],map_location='cpu',weights_only=False);cfg=cp['config'];layers=[];n=152
for _ in range(cfg['num_hidden_layers']):
 layers += [torch.nn.Linear(n,cfg['hidden_dim']),torch.nn.LayerNorm(cfg['hidden_dim']),getattr(torch.nn,cfg['activation'])()];n=cfg['hidden_dim']
layers.append(torch.nn.Linear(n,43));model=torch.nn.Sequential(*layers).eval();model.load_state_dict({k.removeprefix('net.'):v for k,v in cp['model'].items()})
def predict(x):
 with torch.inference_mode():return model(torch.tensor(np.asarray(x),dtype=torch.float32)).numpy()
rows={round(r['time']*60):r for r in map(json.loads,(d/'Pelvis380-nn.jsonl').read_text().splitlines()) if r['actor'].endswith('_C_1')}
keys=[k for k,r in rows.items() if not r['attack'] and r['walk_policy']]
y=predict([rows[k]['lower_input'] for k in keys]);err=float(np.max(np.abs(y-np.array([rows[k]['lower_delta'] for k in keys]))));print('Replay max error',err,flush=True)

result=[]
for f in (373,375,377,379,381,383):
 r=rows[f];pr=rows[f-2];x=np.array(r['lower_input']);pub=np.array(pr['published_lower']);raw=clean(np.array(pr['lower_input'][:41])+pr['lower_delta'][:41]);variants={'baseline':x}
 for sides in ((0,),(1,),(0,1)):
  z=x.copy()
  for i in sides:
   o=18+16*i;carry=rot(pub,o).T@rot(x,o);z[o:o+6]=(rot(raw,o)@carry)[:2].ravel();z[o+76:o+82]=(z[o:o+6]-z[o+41:o+47])/c['pose_delta_scale_final']
  variants['previous_raw_thigh_'+str(sides)]=z
 for name,ix in [('left_thigh_velocity',range(94,100)),('right_thigh_velocity',range(110,116)),('both_thigh_velocities',list(range(94,100))+list(range(110,116)))]:
  z=x.copy();z[list(ix)]=0;variants['zero_'+name]=z
 yy=predict(list(variants.values()));rec={'frame':f,'delta_cm':{k:(v[:3]*100).tolist() for k,v in zip(variants,yy)}};result.append(rec);print(json.dumps(rec),flush=True)
(d/'Pelvis380-replay.json').write_text(json.dumps({'max_replay_error':err,'rows':result},indent=2))
