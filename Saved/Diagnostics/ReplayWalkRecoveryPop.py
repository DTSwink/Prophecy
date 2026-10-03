import os
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import pathlib,json,numpy as np,torch
torch.set_num_threads(1);torch.set_num_interop_threads(1)
p=pathlib.Path(__file__).resolve().parents[2];diag=p/'Saved/Diagnostics'
c=json.loads((p/'Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json').read_text())
cp=torch.load(c['checkpoint_path'],map_location='cpu',weights_only=False)
cfg=cp['config'];layers=[];n=152
for _ in range(cfg['num_hidden_layers']):
 layers += [torch.nn.Linear(n,cfg['hidden_dim']),torch.nn.LayerNorm(cfg['hidden_dim']),getattr(torch.nn,cfg['activation'])()];n=cfg['hidden_dim']
layers.append(torch.nn.Linear(n,43));model=torch.nn.Sequential(*layers).eval()
model.load_state_dict({k.removeprefix('net.'):v for k,v in cp['model'].items()})
def load(tag):return {round(r['time']*60):r for r in map(json.loads,(diag/('FootVibration-nn-'+tag+'.jsonl')).read_text().splitlines()) if r['actor'].endswith('_C_1')}
b=load('walk-recovery-pop');a=load('walk-chain-off')
from ReplayTemperedLeg import rot
geometry={(round(r['t']*60),r['side']):r for r in json.loads((diag/'WalkRecoveryPop-geometry.json').read_text())}
def predict(x):
 with torch.inference_mode():return model(torch.tensor(np.asarray(x),dtype=torch.float32)).numpy()
keys=[k for k,v in b.items() if not v['attack'] and v['walk_policy']]
pred=predict([b[k]['lower_input']for k in keys]);error=float(np.max(abs(pred-np.array([b[k]['lower_delta']for k in keys]))))
print('Exact checkpoint replay max error',error,flush=True);assert error<1e-4
groups={'pelvis':list(range(9)),'kicking_thigh':list(range(18,24)),'supporting_thigh':list(range(34,40)),
 'feet_positions':list(range(9,12))+list(range(25,28)), 'feet_orientation':list(range(12,18))+[24]+list(range(28,34))+[40]}
results=[]
for tick in (117,119,121,123):
 base=np.array(b[tick]['lower_input']);alt=np.array(a[tick]['lower_input'])
 variants={'baseline':base,'chain_off_all':alt}
 for name,ix in groups.items():
  indices=ix+[j+41 for j in ix]+[j+76 if j>=9 else j+82 for j in ix if j<3 or j>=9]
  v=base.copy();v[indices]=alt[indices];variants['swap_'+name]=v
 v=base.copy();v[41:82]=v[:41];v[82:117]=0;variants['zero_incoming_velocity']=v
 if tick>117:
  for sides in ((0,),(1,),(0,1)):
   v=base.copy()
   for side in sides:
    o=18+16*side;g=geometry[(tick-2,side)]
    published=np.array(b[tick-2]['published_lower'])
    carry=rot(published,o).T@rot(base,o)
    values=np.array(g['transported_thigh']);first=values[:3];first/=np.linalg.norm(first)
    second=values[3:]-first*np.dot(first,values[3:]);second/=np.linalg.norm(second)
    transported=np.array([first,second,np.cross(first,second)])
    v[o:o+6]=(transported@carry)[:2].ravel()
    v[o+76:o+82]=(v[o:o+6]-v[o+41:o+47])/c['pose_delta_scale_final']
   variants['remove_only_plane_'+str(sides)]=v
 y=predict(list(variants.values()))
 rec={'tick':tick,'currentZ':base[2]*100,'previousZ':base[43]*100,'velocity_featureZ':base[84],
 'outputs':{name:(yy[:3]*100).tolist() for name,yy in zip(variants,y)}}
 results.append(rec);print(json.dumps(rec),flush=True)
(diag/'WalkRecoveryPop-input-attribution.json').write_text(json.dumps({'replay_error':error,'rows':results},indent=2))
