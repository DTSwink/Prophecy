"""Fetch compact diagnostic results and keep full evidence locally."""
import os,sys,json,shlex
from pathlib import Path
r=Path(__file__).resolve().parents[2];o=r/'Saved/MimicKitEquipment';os.environ['MIMICKIT_STATE_DIR']=str(o);sys.path.insert(0,str(r/'Labs/MimicKitTraining'));import cloud
code="""import json
import numpy as np
from pathlib import Path
r=Path('/workspace/mimickit_trial');o=r/'learning-ablations-20261020'
s=json.loads((o/'queue_status.json').read_text());res={}
for p in o.glob('result_*.json'):
 v=json.loads(p.read_text());res[p.stem[7:]]=v
base=res.get('baseline',{})
if base.get('complete'):
 bm={e['seed']:e for e in base['evaluations']}
 for v in res.values():
  for e in v['evaluations']:
   b=bm.get(e['seed'])
   if b and 'initial_observation' in e and 'initial_observation' in b:
    check={}
    for key in ['initial_observation','initial_velocity']:
     a,z=np.asarray(e[key]),np.asarray(b[key]);check[key+'_max_difference']=float(np.abs(a-z).max());check[key+'_matches']=bool(np.allclose(a,z,atol=1e-6,rtol=1e-6))
    check['getup_exact']=all(e[k]==b[k] for k in ['getup_observation_sha256','getup_velocity_sha256'])
    e['initial_state_verification']=check
for v in res.values():
 for e in v['evaluations']:
  e.pop('initial_observation',None);e.pop('initial_velocity',None)
active=s.get('active');log=(o/(active+'.log')) if active else None
p=json.loads((o/'plan.json').read_text());live=json.loads((r/'runs'/p['run']/'status.json').read_text());backup=r/'runs'/p['run']/'backup_status.json'
print(json.dumps(dict(queue=s,results=res,log_tail=log.read_text()[-2500:] if log and log.exists() else '',live={k:live.get(k) for k in ['state','iteration','samples','training_transitions_per_second']},backup=json.loads(backup.read_text()) if backup.exists() else None)))
"""
data=json.loads(cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=30))
(o/'learning-ablations-results.json').write_text(json.dumps(data,indent=2))
summ={}
for k,v in data['results'].items():
 if not v.get('complete'):summ[k]={'updates':len(v['updates']),'evaluations':len(v['evaluations'])};continue
 counts={}
 for group in [0,1,2]:
  rows=[(e,i) for e in v['evaluations'] for i,g in enumerate(e['group']) if g==group]
  counts[str(group)]=dict(n=len(rows),fail=sum(e['final_done'][i]==1 for e,i in rows),head_reset=sum(e['reasons'][i]==2 for e,i in rows),unfinished=sum(e['end_ticks'][i]==0 for e,i in rows))
 sides={}
 for side in [0,1]:
  for label,lo,hi in [('low',0,.5),('mid',.5,.75),('high',.75,1)]:
   rows=[(e,i) for e in v['evaluations'] for i,g in enumerate(e['group']) if g==2 and e['side'][i]==side and lo<=e['alpha'][i]<hi]
   sides[f'{side}_{label}']=[sum(e['reasons'][i]==2 for e,i in rows),len(rows)]
 summ[k]=dict(groups=counts,sides=sides,seconds=round(v['training_seconds'],1),updates=len(v['updates']),rejected=sum(u['metrics'].get('actor_steps_rejected',0) for u in v['updates']),lr=v['updates'][-1]['metrics'].get('actor_learning_rate') if v['updates'] else None)
(o/'learning-ablations-summary.json').write_text(json.dumps(summ,indent=2))
print(json.dumps(dict(active=data['queue'].get('active'),completed=len(data['queue']['completed']),current=summ.get(data['queue'].get('active')),live=data['live']) if '--compact' in sys.argv else dict(queue=data['queue'],live=data['live'],summary=summ),indent=2))
if data['queue'].get('failed'):print(data['log_tail'])
