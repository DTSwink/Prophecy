"""One requested comparison; no automatic expansion or live-policy changes."""
import json
import os
from pathlib import Path
import shlex
import sys

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud

def directory():
    receipt=OUT/'focused-success-launch.json'
    if receipt.exists():
        return json.loads(receipt.read_text())['directory']
    live=json.loads((OUT/'getup-success-launch.json').read_text())
    return '/workspace/mimickit_trial/focused-success-'+live['run']

def start():
    live=json.loads((OUT/'getup-success-launch.json').read_text())
    cp=live['prepared']['checkpoint']
    variants={}
    for name,noise,lam in [('current',.05,.95),('alternative',.075,.98)]:
        variants[name]=dict(noise=noise,ticks=32,**{'lambda':lam},
                           equivalent_updates=128,seed=13579,evaluate_at_updates=[64,128])
    plan=dict(run=live['run'],checkpoint=cp['preserved_key'],sha256=cp['sha256'],
              actor_lr=1.125e-6,require_success_fix=True,variants=variants,
              variant_timeout_seconds=1200)
    for name in ['audit_learning_ablations.py','run_learning_ablations.py']:
        cloud.rp.scp(cloud.state()['connection'],ROOT/'Labs/MimicKitTraining'/name,
                     '/workspace/mimickit_trial/pipeline/'+name,timeout=30)
    code="""from pathlib import Path
import json,subprocess,shutil,hashlib
r=Path('/workspace/mimickit_trial');o=Path(DIRECTORY);plan=PLAN
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:args=(proc/'cmdline').read_bytes().split(b'\\0')
 except OSError:continue
 if any(x.endswith(b'/run_learning_ablations.py') or x.endswith(b'/audit_learning_ablations.py') for x in args):
  raise RuntimeError('Another comparison is still running')
s=json.loads((r/'runs'/plan['run']/'status.json').read_text())
assert s['state']=='training'
o.mkdir(exist_ok=False);shutil.copyfile(r/'resume.zip',o/'checkpoint.zip')
assert hashlib.sha256((o/'checkpoint.zip').read_bytes()).hexdigest()==plan['sha256']
(o/'plan.json').write_text(json.dumps(plan,indent=2))
with (o/'queue.log').open('wb') as log:
 p=subprocess.Popen([str(r/'venv/bin/python'),'-u',str(r/'pipeline/run_learning_ablations.py'),str(o)],
  stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps(dict(pid=p.pid,directory=str(o),plan=plan)))
""".replace('DIRECTORY',repr(directory())).replace('PLAN',repr(plan))
    receipt=json.loads(cloud.ssh('python -c '+shlex.quote(code),timeout=30))
    (OUT/'focused-success-launch.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))

def inspect():
    code="""from pathlib import Path
import json
o=Path(DIRECTORY);q=json.loads((o/'queue_status.json').read_text());results={}
for p in o.glob('result_*.json'):
 v=json.loads(p.read_text())
 for e in v['evaluations']:
  e.pop('initial_observation',None);e.pop('initial_velocity',None)
 results[p.stem[7:]]=v
print(json.dumps(dict(queue=q,results=results,log_tail=(o/(q['active']+'.log')).read_text()[-1500:] if q.get('active') else '')))
""".replace('DIRECTORY',repr(directory()))
    data=json.loads(cloud.ssh('python -c '+shlex.quote(code),timeout=30))
    (OUT/'focused-success-results.json').write_text(json.dumps(data,indent=2))
    summary={}
    for name,v in data['results'].items():
        groups={}
        for update in sorted({e['evaluation_update'] for e in v['evaluations']}):
            es=[e for e in v['evaluations'] if e['evaluation_update']==update]
            rows=[(e,i) for e in es for i,g in enumerate(e['group']) if g==2]
            loco=[(e,i) for e in es for i,g in enumerate(e['group']) if g==1]
            groups[update]=dict(n=len(rows),success=sum(e['reasons'][i]==2 for e,i in rows),
                failed=sum(e['final_done'][i]==1 for e,i in rows),
                timeout=sum(e['reasons'][i]==3 for e,i in rows),
                loco_failed=sum(e['final_done'][i]==1 for e,i in loco))
        summary[name]=dict(complete=v.get('complete',False),updates=len(v['updates']),
                          seconds=v.get('training_seconds'),evaluations=groups)
    (OUT/'focused-success-summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(dict(queue=data['queue'],summary=summary),indent=2))
    if data['queue'].get('failed'):print(data['log_tail'])

if __name__=='__main__':globals()[sys.argv[1]]()
