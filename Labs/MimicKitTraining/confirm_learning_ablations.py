"""Confirm the strongest screened candidate against current settings on a new seed."""
import os,sys,json,shlex
from pathlib import Path
r=Path(__file__).resolve().parents[2];o=r/'Saved/MimicKitEquipment';os.environ['MIMICKIT_STATE_DIR']=str(o);sys.path.insert(0,str(r/'Labs/MimicKitTraining'));import cloud
rows=json.loads((o/'learning-ablations-comparison.json').read_text());candidates=[x for x in rows if x['name'].startswith('n')];assert len(candidates)==12
best=max(candidates,key=lambda x:(x['success'],x['hard_front_net'],-x['loco_fail']-x['other_fail']))
p=json.loads((o/'learning-ablations-plan.json').read_text());queue=[]
for label,source in [('current','n0.05_t32_l0.95'),('best',best['name'])]:
 key='confirm_'+label+'_s24680';v=dict(p['variants'][source]);v.update(seed=24680,equivalent_updates=128,screened_variant=source);p['variants'][key]=v;queue.append(key)
p['confirmation_selection']=best
code="""import json,subprocess
from pathlib import Path
r=Path('/workspace/mimickit_trial');o=r/'learning-ablations-20261020';s=json.loads((o/'queue_status.json').read_text())
assert s.get('finished') and not s.get('failed') and not s.get('cancelled')
(o/'screening_queue_status.json').write_text(json.dumps(s,indent=2))
p=PLAN
(o/'plan.json').write_text(json.dumps(p,indent=2))
with (o/'confirmation-queue.log').open('wb') as log:
 proc=subprocess.Popen([str(r/'venv/bin/python'),'-u',str(r/'pipeline/run_learning_ablations.py'),str(o),*QUEUE],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps(dict(pid=proc.pid,queue=QUEUE,selected=p['confirmation_selection'])))
""".replace('PLAN',repr(p)).replace('QUEUE',repr(queue))
receipt=json.loads(cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=30))
(o/'learning-ablations-plan.json').write_text(json.dumps(p,indent=2));(o/'learning-ablations-confirmation-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
