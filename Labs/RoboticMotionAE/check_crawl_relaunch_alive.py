import sys,json,shlex
sys.path.insert(0,'Labs/RoboticMotionAE')
import deploy_crawl_only_experiment as x
D=x.OUT/'crawl-relaunch-20261102'
n=json.loads((D/'verification.json').read_text())['run']
code="""import json,time
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
control=json.loads((r/'runtime_control.json').read_text());s=json.loads((p/'status.json').read_text());receipt=json.loads((r/(NAME+'-launch.json')).read_text())
assert control['until_stopped'] and not control['setup_watchdog']
assert not (p/'finished.json').exists() and not (p/'failure.json').exists()
assert s['state']=='training' and time.time()-s['updated_unix']<180
for k in ('pid','exit_guard_pid'):assert NAME.encode() in (Path('/proc')/str(receipt[k])/'cmdline').read_bytes()
print(json.dumps(dict(status={k:s[k] for k in ('state','iteration','samples','updated_unix')},checked_unix=time.time(),until_stopped=True)))
""".replace('NAME',repr(n))
a=json.loads(x.d.cloud.ssh('python -c '+shlex.quote(code),timeout=30))
p=D/'post-release-statuses.json';h=json.loads(p.read_text()) if p.exists() else [];h.append(a);x.d.write(p,h)
print(json.dumps(a))
if len(h)>1 and h[-1]['status']['samples']>h[0]['status']['samples']:x.d.write(D/'post-release-verified.json',dict(run=n,passed=True,status=a['status']))
