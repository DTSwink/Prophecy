"""Reconstruct pelvis-weighted velocity loss from recorded rollout values."""
import json
import deploy_locomotion_branch as d
import restart_locomotion_ae as r

run=json.loads((d.OUT/'active_run.json').read_text())['run']
code='''import json,numpy as np
from pathlib import Path
p=Path('/workspace/mimickit_trial/runs')/RUN
with np.load(p/'replay.npz',allow_pickle=False) as z:
 m=json.loads(str(z['metadata']));results=[]
 for i,row in enumerate(m['replay_rows']):
  suffix='' if i==0 else '_'+str(i)
  v=z['world_velocities'+suffix];delta=v[...,:3]-v[...,6:9]
  cfg=row['perturbed_curriculum'];assert cfg['all_rows_pelvis_velocity_mse_multiplier']==5.
  mix=np.asarray(row['frame_tracking_mix']);mix=mix+cfg.get('ae_mse_weight',0)*(1-mix)
  expected=(np.square(delta).mean((1,2))+4*np.square(delta[:,0]).mean(-1)/delta.shape[1])*row['loss_weights']['linear_velocity_mse']*mix
  actual=z['loss_terms'+suffix][:,1]
  np.testing.assert_allclose(actual[1:],expected[1:],rtol=3e-4,atol=1e-5)
  results.append(dict(row=i,perturbed=row.get('perturbed_row'),idle=row.get('idle_row'),frames=len(actual)-1,max_error=float(np.max(np.abs(actual[1:]-expected[1:])))))
 print(json.dumps(dict(run=RUN,iteration=m['iteration'],rows=results)))
'''.replace('RUN',repr(run))
result=json.loads(r.remote(code));d.save('pelvis5-replay-verification',result);print(json.dumps(result))
