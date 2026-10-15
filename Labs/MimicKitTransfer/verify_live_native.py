import os,json
from pathlib import Path
os.environ['MIMICKIT_TRANSFER_OUT']=str(Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913')
for k in list(os.environ):
 if k.startswith('TRANSFER_'):del os.environ[k]
from native_probe import OUT,Native,np,R,actor,observation,keys,offsets
raw=np.load(OUT/'coupled_live_dt_batch/raw.npz');rows=[]
for phase in range(4):
 n=Native(raw['first_physical'][phase]);current=np.array(n.initial['bodies']);states=[current];dist=[]
 try:
  np.testing.assert_allclose(current,raw['first_physical'][phase],atol=1e-5,rtol=1e-5)
  for tick in range(1,300):
   a=actor(observation(current,raw['obs'][tick,phase,-5:]));current=np.array(n.request('step '+' '.join(map(str,a)))['bodies']);states.append(current)
   target=raw['targets'][tick,phase].copy();target[:,:2]+=current[0,:2]-target[0,:2]
   actual=current[keys,:3]+R.from_quat(current[keys,3:7]).apply(offsets);desired=target[keys,:3]+R.from_quat(target[keys,3:7]).apply(offsets)
   dist.append(np.linalg.norm(actual-desired,axis=1))
   if max(dist[-1])>.27:break
 finally:n.close()
 row=dict(phase=phase/4,ticks=len(dist),passed=len(dist)==299,max_distance_m=float(np.max(dist)));rows.append(row);print(json.dumps(row),flush=True)
 np.savez_compressed(OUT/f'causal_transfer/live_native_{phase}.npz',states=states,dist=dist)
(OUT/'causal_transfer/live_native.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
