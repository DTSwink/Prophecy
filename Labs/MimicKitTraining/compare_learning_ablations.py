"""Paired comparison of completed learning trials, with strict start matching."""
import json
import numpy as np
import zipfile,yaml
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'Saved/MimicKitEquipment'
with zipfile.ZipFile(out/'getup-skew-source.zip') as archive:cfg=yaml.safe_load(archive.read('prepared/env_config.yaml'))
idle_rows=round(512*cfg['idle_row_fraction']);recovery_count=round(idle_rows*cfg['idle_recovery']['fraction'])
recovery_ids=set(np.floor((np.arange(recovery_count,dtype=np.float32)+.5)*idle_rows/recovery_count).astype(int).tolist())
data=json.loads((out/'learning-ablations-results.json').read_text())['results']
base=data.get('baseline',{})
if not base.get('complete'):raise SystemExit('Baseline pending')
base_e={e['seed']:e for e in base['evaluations']};rows=[]
for name,v in data.items():
 if not v.get('complete'):continue
 gains=losses=hard_gains=hard_losses=success=loco_fail=other_fail=0
 normal_getup_fail=normal_loco_fail=idle_fail=0
 for e in v['evaluations']:
  b=base_e[e['seed']]
  for key in ['initial_position_sha256','group','side','alpha','row_ids']:
   assert e[key]==b[key],(name,e['seed'],key)
  check=e.get('initial_state_verification')
  if check:
   assert check['initial_observation_matches'] and check['initial_velocity_matches'] and check['getup_exact'],(name,check)
  else:assert name=='uniform_control', 'Missing comparison arrays'
  for i,g in enumerate(e['group']):
   if g==2:
    good=e['reasons'][i]==2;old=b['reasons'][i]==2
    success+=good;gains+=good and not old;losses+=old and not good
    if e['side'][i]==0 and e['alpha'][i]>=.5:
     hard_gains+=good and not old;hard_losses+=old and not good
   elif g==1:loco_fail+=e['final_done'][i]==1
   else:
    failed=e['final_done'][i]==1;other_fail+=failed
    if e['row_ids'][i] in recovery_ids:normal_getup_fail+=failed
    elif e['row_ids'][i]>=idle_rows:normal_loco_fail+=failed
    else:idle_fail+=failed
 good_rows=[(e,i) for e in v['evaluations'] for i,g in enumerate(e['group']) if g==2 and e['reasons'][i]==2]
 mean_tick=float(np.mean([e['end_ticks'][i] for e,i in good_rows]))
 mean_cost=float(np.mean([e['end_position_cost'][i] for e,i in good_rows]))
 updates=v['updates']
 row=dict(name=name,success=success,gained=gains,lost=losses,hard_front_net=hard_gains-hard_losses,loco_fail=loco_fail,other_fail=other_fail,normal_getup_fail=normal_getup_fail,normal_loco_fail=normal_loco_fail,idle_fail=idle_fail,
  training_seconds=round(v['training_seconds'],2),transitions=v['training_transitions'],
  accepted=sum(u['metrics'].get('actor_steps_accepted',0) for u in updates),rejected=sum(u['metrics'].get('actor_steps_rejected',0) for u in updates),
  final_lr=updates[-1]['metrics'].get('actor_learning_rate') if updates else None,starts_verified=('strict tolerance' if name!='uniform_control' else 'preliminary control; numerical reset audit'),mean_success_ticks=mean_tick,mean_success_position_cost=mean_cost)
 rows.append(row)
rows.sort(key=lambda x:x['name']);(out/'learning-ablations-comparison.json').write_text(json.dumps(rows,indent=2))
print('name | get-up successes/928 | gained/lost | hard-front net | loco failures/432 | other failures/688 | train seconds | rejected')
for x in rows:print(f"{x['name']} | {x['success']} | {x['gained']}/{x['lost']} | {x['hard_front_net']:+} | {x['loco_fail']} | {x['other_fail']} | {x['training_seconds']} | {x['rejected']}")
