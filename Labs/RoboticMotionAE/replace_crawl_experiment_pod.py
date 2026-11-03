"""Explicitly authorized one-pod replacement; keeps stopped original disk."""
import json,sys,time,shutil,subprocess
from pathlib import Path
import deploy_crawl_only_experiment as x
d=x.d; OUT=x.OUT; D=x.D

def allocate():
    pods=d.cloud.rp.request_json('GET','/pods')
    original=next(p for p in pods if p['id']=='vpv6saq7zyooak')
    assert original['desiredStatus']=='EXITED'
    assert not [p for p in pods if p.get('name','').startswith('mimickit-crawl-only-replacement-20261102')], 'Reconcile replacement first'
    current=d.cloud.state();assert current['pod_id']==original['id']
    archive=D/'stopped-original';archive.mkdir(exist_ok=True)
    for name in ('pod.json','runtime_control.json','guards.json','active_run.json','observers.json'):
        if (OUT/name).exists():shutil.copy2(OUT/name,archive/name)
    d.write(archive/'provider.json',{k:original.get(k) for k in ('id','name','desiredStatus','costPerHr')})
    # Package here is setup input only; production launch requires resumed preflight.
    inventory=d.P/'source-inventory.json'
    receipt=OUT/'source-receipt.json'
    bundled=False
    if inventory.exists() and receipt.exists() and (OUT/'source.zip').exists():
        saved=json.loads(receipt.read_text()); inv=json.loads(inventory.read_text())
        actual={p.relative_to(d.P).as_posix():d.sha(p) for p in d.P.rglob('*')
                if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='source-inventory.json'}
        bundled=saved.get('verified') and saved['sha256']==d.sha(OUT/'source.zip') and inv==actual
    if not bundled:d.bundle()
    (OUT/'pod.json').unlink()
    errors=[]
    for kind in ('COMMUNITY','SECURE'):
        try:
            d.cloud.allocate('NVIDIA RTX 4000 Ada Generation',.28,kind,1200,'mimickit-crawl-only-replacement-20261102-'+kind.lower())
            break
        except Exception as e:
            errors.append(str(e));print(kind,str(e)[:300],flush=True)
            if (OUT/'pod.json').exists():raise
    else:
        shutil.copy2(archive/'pod.json',OUT/'pod.json')
        d.write(D/'replacement-unavailable.json',dict(time=time.time(),errors=errors))
        raise RuntimeError('No replacement capacity; original state restored')
    state=d.cloud.state()
    d.write(OUT/'runtime_control.json',dict(pod_id=state['pod_id'],hard_stop_unix=time.time()+1200,setup_watchdog=True))
    with (OUT/'local-guard.log').open('ab') as log:
        proc=subprocess.Popen([sys.executable,str(d.ROOT/'Labs/MimicKitTraining/local_guard.py')],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    d.write(OUT/'guards.json',dict(local_guard=proc.pid))
    d.write(D/'replacement-pod.json',state)

def upload_resume():
    info=json.loads((D/'main-resume-checkpoint.json').read_text())
    assert d.sha(info['local'])==info['sha256']
    import shlex
    code="""from pathlib import Path
import json,hashlib,boto3
from botocore.config import Config
r=Path('/workspace/mimickit_trial');info=INFO
p=Path(info['path']);p.parent.mkdir(parents=True,exist_ok=True)
if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=info['sha256']:
 control=json.loads((r/'private.json').read_text())
 client=boto3.client('s3',**control['s3'],config=Config(connect_timeout=10,read_timeout=30,retries={'total_max_attempts':2}))
 temp=p.with_suffix('.part');client.download_file('aj7d2jzwuq',info['backup']['key'],str(temp))
 assert hashlib.sha256(temp.read_bytes()).hexdigest()==info['sha256']
 temp.replace(p)
print('Checkpoint20414 SHA verified')
""".replace('INFO',repr(info))
    print(d.cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=120))
    d.write(D/'replacement-resume-verified.json',dict(pod=d.cloud.state()['pod_id'],path=info['path'],sha256=info['sha256']))
    print('Safe checkpoint20414 uploaded and verified',flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
