"""Checkpoint-preserving restart for the user-calibrated recovery pelvis ceiling."""
import hashlib
import json
import shlex
import sys
import time
import zipfile
from pathlib import Path

import resume_getup_success as r


def stop():
    active = json.loads((r.OUT/'active_run.json').read_text())
    if active['pod'] != r.cloud.state()['pod_id'] or active['run'] != '20261021_194738_uefn_getup_success_gates_1024':
        raise ValueError('Unexpected active recovery run')
    code = '''import os,signal,json,subprocess
from pathlib import Path
r=Path('/workspace/mimickit_trial');name=NAME
receipt=json.loads((r/(name+'-launch.json')).read_text());guard=receipt['exit_guard_pid']
cmd=(Path('/proc')/str(guard)/'cmdline').read_bytes()
assert b'failure_stop.py' in cmd and name.encode() in cmd
(r/'pelvis_ceiling_verified').unlink(missing_ok=True)
watch="import sys,time,json;from pathlib import Path;sys.path.insert(0,'/workspace/mimickit_trial/pipeline');from billing_stop import stop_and_confirm;r=Path('/workspace/mimickit_trial');end=time.time()+600;c=json.loads((r/'private.json').read_text())\\nwhile time.time()<end and not (r/'pelvis_ceiling_verified').exists():time.sleep(2)\\nif not (r/'pelvis_ceiling_verified').exists():stop_and_confirm(c['pod_id'],c['runpod_api_key'],r/'pelvis_ceiling_timeout.json','Recovery pelvis-ceiling restart exceeded ten minutes')"
with (r/'pelvis_ceiling_watch.log').open('ab') as log:
 p=subprocess.Popen([str(r/'venv/bin/python'),'-c',watch],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
os.kill(guard,signal.SIGTERM)
(r/'runs'/name/'stop.request').touch()
print(json.dumps(dict(run=name,watchdog=p.pid)))
'''.replace('NAME', repr(active['run']))
    result = json.loads(r.remote(code))
    (r.OUT/'pelvis-ceiling-handoff.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


def preserve():
    old = json.loads((r.OUT/'pelvis-ceiling-handoff.json').read_text())['run']
    code = '''import json,time,hashlib,shutil
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
for _ in range(20):
 if (p/'finished.json').exists() or (p/'failure.json').exists():break
 time.sleep(2)
if not (p/'finished.json').exists():raise RuntimeError('Final checkpoint not ready')
b=json.loads((p/'backup_status.json').read_text())
assert b['key'].endswith('_final.zip')
f=p/Path(b['key']).name
assert hashlib.sha256(f.read_bytes()).hexdigest()==b['sha256']
shutil.copyfile(f,r/'resume.zip')
print(json.dumps(dict(backup=b,finished=json.loads((p/'finished.json').read_text()))))
'''.replace('NAME', repr(old))
    result = json.loads(r.remote(code, timeout=50))
    cp = result['backup']
    path = r.OUT/'preserved-latest'/old/Path(cp['key']).name
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.part')
    r.cloud.s3().download_file(r.cloud.rp.VOLUME_ID, cp['key'], str(tmp))
    if hashlib.sha256(tmp.read_bytes()).hexdigest() != cp['sha256']:
        raise RuntimeError('Latest checkpoint download checksum mismatch')
    with zipfile.ZipFile(tmp) as z:
        if z.testzip() is not None:raise RuntimeError('Latest checkpoint ZIP integrity failure')
    tmp.replace(path)
    cp.update(local=str(path), preserved_key=cp['key'], verified_local_unix=time.time())
    result['backup'] = cp
    (r.OUT/'pelvis-ceiling-preserved.json').write_text(json.dumps(result, indent=2))
    plan = json.loads((r.OUT/'getup-pelvis-ceiling-prepared.json').read_text())
    plan['checkpoint'] = cp
    (r.OUT/'getup-success-prepared.json').write_text(json.dumps(plan, indent=2))
    print(json.dumps(result), flush=True)


def deploy():
    plan = json.loads((r.OUT/'getup-success-prepared.json').read_text())
    code = '''import json,hashlib,boto3
from pathlib import Path
r=Path('/workspace/mimickit_trial');cfg=json.loads((r/'private.json').read_text())
c=boto3.client('s3',**cfg['s3']);p=r/'source.next.zip'
c.download_file('aj7d2jzwuq',KEY,str(p))
assert hashlib.sha256(p.read_bytes()).hexdigest()==SHA
p.replace(r/'source.zip');print('Source verified')
'''.replace('KEY', repr(plan['source']['key'])).replace('SHA', repr(plan['source']['sha256']))
    print(r.cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code), timeout=60), flush=True)
    r.launch()


if __name__ == '__main__':
    globals()[sys.argv[1]]()
