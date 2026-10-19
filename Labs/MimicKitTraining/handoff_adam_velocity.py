"""Stage this approved migration on the existing pod; retain its deadline."""
import json,os,shlex,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud


def remote(code,timeout=45):
    return cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=timeout)


def main():
    source=json.loads((OUT/'adam-velocity-source-verified.json').read_text())
    cp=json.loads((OUT/'pre-collapse-38799.json').read_text())
    active=json.loads((OUT/'active_run.json').read_text());old=active['run']
    assert active['pod']==cloud.state()['pod_id']=='n5esp2rc3dvxc4'
    hard=json.loads((OUT/'runtime_control.json').read_text())['hard_stop_unix']
    assert hard==1792393912.192196 and hard-time.time()>600
    stage="""import json,hashlib,zipfile,io
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial');c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
p=r/'adam_velocity_stage';p.mkdir(exist_ok=True)
for key,digest,name in ITEMS:
 data=c.get_object(Bucket='aj7d2jzwuq',Key=key)['Body'].read()
 assert hashlib.sha256(data).hexdigest()==digest
 (p/name).write_bytes(data)
 if name=='source.zip':
  with zipfile.ZipFile(io.BytesIO(data)) as z:z.extractall(p)
print('Source and pre-collapse checkpoint staged and hash-verified',flush=True)
""".replace('ITEMS',repr([(source['key'],source['sha256'],'source.zip'),(cp['key'],cp['sha256'],'resume.zip')]))
    print(remote(stage,90),flush=True)
    handoff="""import json,time,subprocess,os,signal
from pathlib import Path
r=Path('/workspace/mimickit_trial');name=OLD
receipt=json.loads((r/(name+'-launch.json')).read_text());guard=receipt['exit_guard_pid']
args=(Path('/proc')/str(guard)/'cmdline').read_bytes()
assert b'failure_stop.py' in args and name.encode() in args
watch="import sys,time,json; from pathlib import Path; sys.path.insert(0,'/workspace/mimickit_trial/pipeline'); from billing_stop import stop_and_confirm; r=Path('/workspace/mimickit_trial'); end=time.time()+600; p=r/'adam_handoff_complete'; c=json.loads((r/'private.json').read_text()); \\nwhile time.time()<end and not p.exists():time.sleep(2)\\nif not p.exists():stop_and_confirm(c['pod_id'],c['runpod_api_key'],r/'adam_handoff_billing_stop.json','Adam migration handoff timed out')"
(r/'adam_handoff_complete').unlink(missing_ok=True)
with (r/'adam-handoff-guard.log').open('ab') as log:
 w=subprocess.Popen([str(r/'venv/bin/python'),'-c',watch],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
os.kill(guard,signal.SIGTERM)
(r/'runs'/name/'stop.request').touch()
print(json.dumps(dict(watchdog=w.pid,old_run=name)),flush=True)
""".replace('OLD',repr(old))
    print(remote(handoff),flush=True)
    end=time.time()+150
    while time.time()<end:
        code="""import json
from pathlib import Path
r=Path('/workspace/mimickit_trial');name=OLD;p=r/'runs'/name
pid=json.loads((r/(name+'-launch.json')).read_text())['pid'];proc=Path('/proc')/str(pid)/'cmdline'
exited=not proc.exists() or name.encode() not in proc.read_bytes()
b=p/'backup_status.json';f=p/'finished.json'
print(json.dumps(dict(exited=exited,finished=f.exists(),backup=json.loads(b.read_text()) if b.exists() else None)))
""".replace('OLD',repr(old))
        status=json.loads(remote(code))
        if status['exited'] and status['finished'] and status['backup']['key'].endswith('_final.zip'):break
        time.sleep(5)
    else:raise TimeoutError('Old trainer did not save and finish; bounded watchdog remains armed')
    (OUT/'adam-velocity-handoff-final.json').write_text(json.dumps(status,indent=2))
    install="""import json,shutil,subprocess
from pathlib import Path
r=Path('/workspace/mimickit_trial');stage=r/'adam_velocity_stage'
for p in stage.rglob('*'):
 if p.is_file():
  dest=r/p.relative_to(stage);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
private=json.loads((r/'private.json').read_text());private['resume_checkpoint']=CP
(r/'private.json').write_text(json.dumps(private));(r/'stop.request').unlink(missing_ok=True)
with (r/'adam-velocity-preflight.log').open('wb') as log:
 p=subprocess.Popen([str(r/'venv/bin/python'),'-u',str(r/'pipeline/preflight_adam_velocity.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(preflight_pid=p.pid,old_final=FINAL)),flush=True)
""".replace('CP',repr(cp)).replace('FINAL',repr(status['backup']))
    print(remote(install),flush=True)


if __name__=='__main__':main()
