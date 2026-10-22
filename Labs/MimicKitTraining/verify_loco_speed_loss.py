"""Reconstruct the new soft cost and reward from actual replay states."""
import json
import sys
import deploy_locomotion_branch as d
import restart_locomotion_ae as r


def replay():
    run=json.loads((d.OUT/'active_run.json').read_text())['run']
    code='''import json,numpy as np
from pathlib import Path
p=Path('/workspace/mimickit_trial/runs')/RUN/'replay.npz'
if not p.exists():
 print(json.dumps({'ready':False}))
else:
 with np.load(p,allow_pickle=False) as z:
  m=json.loads(str(z['metadata']));names=m['names'];ids=[names.index(x) for x in ['right_foot','left_foot','right_hand','left_hand']]
  checked=[];total_continued=0;max_error=0.
  for i,row in enumerate(m['replay_rows']):
   suffix='' if i==0 else '_'+str(i)
   terms=z['loss_terms'+suffix];j=row['loss_term_names'].index('extremity_speed_excess')
   if not row.get('perturbed_row'):
    assert np.all(terms[:,j]==0)
    continue
   assert row['extremity_speed_termination']==False
   pos=z['pose'+suffix][...,:3];vel=z['world_velocities'+suffix][...,:3];ang=z['world_velocities'+suffix][...,3:6]
   relative=vel[:,ids]-vel[:,:1]-np.cross(ang[:,:1],pos[:,ids]-pos[:,:1])
   excess=np.maximum(np.linalg.norm(relative,axis=-1)-np.array(row['extremity_speed_limits_m_s']),0)
   predicted=np.square(excess).mean(-1)*row['extremity_speed_loss_weight'];predicted[0]=0
   np.testing.assert_allclose(terms[:,j],predicted,rtol=3e-4,atol=1e-5)
   max_error=max(max_error,float(np.max(np.abs(terms[:,j]-predicted))))
   data=z['data'+suffix];continued=int(((predicted>0)&(data[:,0]==0)).sum());total_continued+=continued
   # Existing loco failure cost still applies to COM2 failures only.
   reward=1/(1+terms.sum(-1))-(data[:,0]==1)*float(row.get('loco_failure_penalty',0))
   np.testing.assert_allclose(data[1:,2],reward[1:],rtol=3e-4,atol=1e-5)
   checked.append(dict(row=i,frames=len(predicted)-1,overspeed_frames=int((predicted>0).sum()),continued_overspeed_frames=continued))
  print(json.dumps(dict(ready=True,iteration=m['iteration'],rows=checked,continued_overspeed_frames=total_continued,max_loss_error=max_error)))
'''.replace('RUN',repr(run))
    result=json.loads(r.remote(code));d.save('speed-loss-replay-verification',result);print(json.dumps(result))


if __name__=='__main__':replay()
