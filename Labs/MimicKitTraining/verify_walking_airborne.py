"""Check the actual saved loss/reward and masks after the restart."""
import json
import deploy_locomotion_branch as d
import restart_locomotion_ae as r

run=json.loads((d.OUT/'active_run.json').read_text())['run']
code='''import sys,json,numpy as np,torch,time
from pathlib import Path
sys.path.insert(0,'/workspace/mimickit_trial/pipeline')
from walking_airborne import foot_box_bottoms,airborne_cost
p=Path('/workspace/mimickit_trial/runs')/RUN
for _ in range(10):
 if (p/'replay.npz').exists() and (p/'backup_status.json').exists():break
 time.sleep(3)
results=[]
with np.load(p/'replay.npz',allow_pickle=False) as z:
 m=json.loads(str(z['metadata']))
 for i,row in enumerate(m['replay_rows']):
  suffix='' if i==0 else '_'+str(i);cfg=row['perturbed_curriculum'];boxes=cfg['walking_foot_boxes'];weight=cfg['walking_airborne_weight']
  ids=[m['names'].index(b['bone']) for b in boxes];pose=torch.tensor(z['pose'+suffix][:,ids])
  centers=torch.tensor([b['center'] for b in boxes]);axes=torch.tensor([b['half_axes'] for b in boxes])
  bottoms=foot_box_bottoms(pose[...,:3],pose[...,3:],centers,axes)
  walk='_Walk_' in row['motion_file'] and not row.get('recovery_row',False)
  expected=airborne_cost(bottoms,torch.full((len(pose),),walk))*weight
  names=row['loss_term_names'];terms=z['loss_terms'+suffix];actual=terms[:,names.index('walking_airborne')]
  np.testing.assert_allclose(actual[1:],expected.numpy()[1:],rtol=1e-3,atol=5e-5)
  cols=[j for j,n in enumerate(names) if not (n=='auto_phase' and row.get('auto_phase_scope'))]
  reward=1/(1+terms[1:,cols].sum(-1));data=z['data'+suffix]
  reward-=float(row.get('loco_failure_penalty',0))*(data[1:,0]==1)
  np.testing.assert_allclose(reward,data[1:,2],atol=1e-6)
  results.append(dict(row=i,walk=walk,perturbed=row.get('perturbed_row'),positive_ticks=int((actual[1:]>0).sum()),max_loss=float(actual.max())))
 # Small GPU microbenchmark of the production height/loss math for 1024 worlds.
 pp=torch.ones(1024,2,3,device='cuda');qq=torch.zeros(1024,2,4,device='cuda');qq[:,:,-1]=1
 cc=centers.cuda();aa=axes.cuda();mask=torch.ones(1024,dtype=torch.bool,device='cuda')
 for _ in range(10):airborne_cost(foot_box_bottoms(pp,qq,cc,aa),mask)
 torch.cuda.synchronize();start=time.perf_counter()
 for _ in range(100):airborne_cost(foot_box_bottoms(pp,qq,cc,aa),mask)
 torch.cuda.synchronize();ms=(time.perf_counter()-start)*10
print(json.dumps(dict(run=RUN,iteration=m['iteration'],rows=results,detector_ms_per_1024_worlds=ms)))
'''.replace('RUN',repr(run))
result=json.loads(r.remote(code,timeout=60));d.save('walking-airborne-live-verification',result);print(json.dumps(result),flush=True)
