import sys,json,shlex
sys.path.insert(0,'Labs/RoboticMotionAE')
import deploy_crawl_only_experiment as x
D=x.OUT/'crawl-relaunch-20261102';x.c.D=D
r=x.c.audit();history=json.loads((D/'advancing-statuses.json').read_text())
assert len(history)>1 and history[-1]['samples']>history[0]['samples']
assert r['resume']['iteration_offset']==20426 and r['resume']['optimizer_restored'] and r['resume']['normalizer_restored']
assert len(r['replay_rows'])==8 and r['model']['_obs_norm._mean']==[160]
name=r['run']
code="""import sys,json,hashlib
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
assert not (p/'finished.json').exists()
assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in json.loads((r/'source-inventory.json').read_text()).items())
sys.path.insert(0,str(r/'disabled-preflight'))
from verify_disabled_replay import verify
print(json.dumps(verify(p/'replay.npz')))
""".replace('NAME',repr(name))
x.d.write(D/'live-replay-verified.json',json.loads(x.d.cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=45)))
x.d.verify();x.d.write(D/'verification.json',dict(run=name,passed=True,status=r['status'],resume=r['resume'],checkpoint_backup_verified=True))
