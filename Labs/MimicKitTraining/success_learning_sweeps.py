"""Isolated follow-up sweeps under corrected success accounting."""
import json,os,shlex,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
def remote_directory():
    live=json.loads((OUT/'getup-success-launch.json').read_text())
    return '/workspace/mimickit_trial/success-sweeps-'+live['run']
def start():
    remote=remote_directory()
    live=json.loads((OUT/'getup-success-launch.json').read_text())
    cp=live['prepared']['checkpoint']
    variants={'baseline':dict(noise=.05,ticks=32,**{'lambda':.95},equivalent_updates=0)}
    for noise in [.05,.075]:
        for lam in [.95,.98]:
            variants[f'n{noise}_l{lam}']=dict(noise=noise,ticks=32,**{'lambda':lam},equivalent_updates=64,seed=13579)
    plan=dict(run=live['run'],checkpoint=cp['preserved_key'],sha256=cp['sha256'],actor_lr=1.125e-6,variants=variants)
    for file in ['audit_learning_ablations.py','run_learning_ablations.py']:
        cloud.rp.scp(cloud.state()['connection'],ROOT/'Labs/MimicKitTraining'/file,'/workspace/mimickit_trial/pipeline/'+file,timeout=45)
    code="""import json,subprocess,shutil,hashlib
from pathlib import Path
r=Path('/workspace/mimickit_trial');o=Path(REMOTE);o.mkdir(exist_ok=False)
p=PLAN
s=json.loads((r/'runs'/p['run']/'status.json').read_text());assert s['state']!='failed'
assert (r/'runs'/p['run']/'backup_status.json').exists()
shutil.copyfile(r/'resume.zip',o/'checkpoint.zip')
assert hashlib.sha256((o/'checkpoint.zip').read_bytes()).hexdigest()==p['sha256']
(o/'plan.json').write_text(json.dumps(p,indent=2))
with (o/'queue.log').open('wb') as log:
 proc=subprocess.Popen([str(r/'venv/bin/python'),'-u',str(r/'pipeline/run_learning_ablations.py'),str(o)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps(dict(pid=proc.pid,plan=p)))
""".replace('REMOTE',repr(remote)).replace('PLAN',repr(plan))
    result=json.loads(cloud.ssh('python -c '+shlex.quote(code),timeout=30))
    (OUT/'success-sweeps-launch.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
def inspect():
    remote=remote_directory()
    code="""import json
from pathlib import Path
o=Path(REMOTE);s=json.loads((o/'queue_status.json').read_text());results={}
for p in o.glob('result_*.json'):
 v=json.loads(p.read_text())
 for e in v['evaluations']:
  e.pop('initial_observation',None);e.pop('initial_velocity',None)
 results[p.stem[7:]]=v
active=s.get('active');log=o/(active+'.log') if active else o/'queue.log'
print(json.dumps(dict(queue=s,results=results,log_tail=log.read_text()[-2000:] if log.exists() else '')))
""".replace('REMOTE',repr(remote))
    data=json.loads(cloud.ssh('python -c '+shlex.quote(code),timeout=30));summary={}
    for name,v in data['results'].items():
        rows=[(e,i) for e in v['evaluations'] for i,g in enumerate(e['group']) if g==2]
        loco=[(e,i) for e in v['evaluations'] for i,g in enumerate(e['group']) if g==1]
        summary[name]=dict(complete=v.get('complete',False),updates=len(v['updates']),getup_n=len(rows),
            head_success=sum(e['reasons'][i]==2 for e,i in rows),timeouts=sum(e['reasons'][i]==3 for e,i in rows),
            loco_failures=sum(e['final_done'][i]==1 for e,i in loco),seconds=v.get('training_seconds'),
            rejected=sum(x['metrics'].get('actor_steps_rejected',0) for x in v['updates']))
    (OUT/'success-sweeps-results.json').write_text(json.dumps(data,indent=2))
    (OUT/'success-sweeps-summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(dict(queue=data['queue'],summary=summary),indent=2))
    if data['queue'].get('failed'):print(data['log_tail'])
if __name__=='__main__':globals()[sys.argv[1]]()
