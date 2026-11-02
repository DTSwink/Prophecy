"""Checkpoint-preserving restart of the single owned slow-loco trainer."""
import json,sys,time,shlex,zipfile
from pathlib import Path
import deploy_slow_policy as d
TAG='loop'

def stop():
    assert json.loads((d.OUT/'loop-termination-test.json').read_text())['passed']
    if TAG=='retarget':assert json.loads((d.OUT/'retarget-repair-20261031/validation.json').read_text())['passed']
    active=json.loads((d.OUT/'active_run.json').read_text())
    d.write(d.OUT/(TAG+'-previous-run.json'),active)
    control=dict(pod_id=d.cloud.state()['pod_id'],hard_stop_unix=time.time()+1200,setup_watchdog=True)
    d.write(d.OUT/'runtime_control.json',control)
    d.cloud.rp.scp(d.cloud.state()['connection'],d.OUT/'runtime_control.json','/workspace/mimickit_trial/runtime_control.json',timeout=30)
    code='''from pathlib import Path
import json,os,signal
r=Path('/workspace/mimickit_trial');name=NAME
a=json.loads((r/(name+'-launch.json')).read_text())
pid=a['exit_guard_pid'];args=(Path('/proc')/str(pid)/'cmdline').read_bytes().split(bytes([0]))
assert name.encode() in args and str(r/'pipeline/failure_stop.py').encode() in args
os.kill(pid,signal.SIGTERM)
(r/'runs'/name/'stop.request').write_text(REASON)
print('Graceful stop requested')
'''.replace('NAME',repr(active['run'])).replace('REASON',repr('Authorized restart: '+TAG+' slow-loco targets'))
    print(d.cloud.ssh('python -c '+shlex.quote(code),timeout=30))

def launch():
    old=json.loads((d.OUT/(TAG+'-previous-run.json')).read_text());name=old['run']
    code='''from pathlib import Path
import json
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
assert (p/'finished.json').exists(),'Trainer still stopping'
assert not (p/'failure.json').exists()
a=json.loads((r/(NAME+'-launch.json')).read_text());proc=Path('/proc')/str(a['pid'])/'cmdline'
assert not proc.exists() or not proc.read_bytes(),'Trainer still alive'
print((p/'backup_status.json').read_text())
'''.replace('NAME',repr(name))
    latest=json.loads(d.cloud.ssh('python -c '+shlex.quote(code),timeout=30))
    local=d.OUT/'preserved-latest'/name/Path(latest['key']).name;local.parent.mkdir(parents=True,exist_ok=True)
    d.cloud.s3().download_file(d.cloud.rp.VOLUME_ID,latest['key'],str(local))
    assert local.stat().st_size==latest['bytes'] and d.sha(local)==latest['sha256']
    with zipfile.ZipFile(local) as z:assert z.testzip() is None
    d.write(d.OUT/(TAG+'-resume-checkpoint.json'),dict(**latest,local=str(local),previous_run=name))
    d.cloud.rp.scp(d.cloud.state()['connection'],d.OUT/'source.zip','/workspace/mimickit_trial/source-'+TAG+'.zip',timeout=45)
    code='''from pathlib import Path
import hashlib,zipfile
r=Path('/workspace/mimickit_trial');p=r/'SOURCE_NAME'
assert hashlib.sha256(p.read_bytes()).hexdigest()==SOURCE_HASH
with zipfile.ZipFile(p) as z:z.extractall(r)
cp=r/'runs'/OLD_RUN/ARCHIVE
assert hashlib.sha256(cp.read_bytes()).hexdigest()==CHECKPOINT_HASH
print(str(cp))
'''.replace('SOURCE_NAME','source-'+TAG+'.zip').replace('SOURCE_HASH',repr(d.sha(d.OUT/'source.zip'))).replace('OLD_RUN',repr(name)).replace('ARCHIVE',repr(local.name)).replace('CHECKPOINT_HASH',repr(latest['sha256']))
    cp=d.cloud.ssh('python -c '+shlex.quote(code),timeout=30).strip()
    d.launch(cp)

if __name__=='__main__':
    TAG=sys.argv[2] if len(sys.argv)>2 else 'loop'
    assert TAG in ('loop','retarget')
    globals()[sys.argv[1]]()
