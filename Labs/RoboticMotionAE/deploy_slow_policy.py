"""Owned slow-loco Runpod deployment with bounded setup and exit billing guard."""
import os,sys,json,time,hashlib,zipfile,tempfile,shlex,subprocess
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/MimicKitSlowLoco';P=OUT/'package'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
sys.path.insert(0,str(ROOT/'Labs/MimicKitTraining'))
import cloud
from local_process import ServiceLock
write=lambda p,x:Path(p).write_text(json.dumps(x,indent=2))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
FAR=253402300799

def bundle():
    assert json.loads((OUT/'preflight.json').read_text())['passed']
    inv={p.relative_to(P).as_posix():sha(p) for p in P.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='source-inventory.json'}
    write(P/'source-inventory.json',inv)
    with zipfile.ZipFile(OUT/'source.zip','w',zipfile.ZIP_DEFLATED) as z:
        for n in inv:z.write(P/n,n)
        z.write(P/'source-inventory.json','source-inventory.json')
    body=(OUT/'source.zip').read_bytes();digest=sha(OUT/'source.zip');key='mimickit/pipeline_20261014/slowloco/source_'+digest[:12]+'.zip'
    c=cloud.s3();c.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=body)
    assert hashlib.sha256(c.get_object(Bucket=cloud.rp.VOLUME_ID,Key=key)['Body'].read()).hexdigest()==digest
    write(OUT/'source-receipt.json',dict(key=key,sha256=digest,bytes=len(body),verified=True))
    print('source verified',digest,flush=True)

def allocate():
    assert not (OUT/'pod.json').exists(),'Reconcile retained slow-loco pod before retry'
    assert json.loads((OUT/'source-receipt.json').read_text())['verified']
    for kind in ('COMMUNITY','SECURE'):
        try:
            cloud.allocate('NVIDIA RTX 4000 Ada Generation',.28,kind,1200,'mimickit-slowloco-20261031-'+kind.lower())
            break
        except Exception as e:
            if (OUT/'pod.json').exists():raise
            print(kind,str(e)[:300],flush=True)
    else:raise RuntimeError('RTX 4000 Ada unavailable in Community and Secure; no GPU allocated')
    s=cloud.state();write(OUT/'runtime_control.json',dict(pod_id=s['pod_id'],hard_stop_unix=time.time()+1200,setup_watchdog=True))
    with (OUT/'local-guard.log').open('ab') as log:
        proc=subprocess.Popen([sys.executable,str(ROOT/'Labs/MimicKitTraining/local_guard.py')],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    write(OUT/'guards.json',dict(local_guard=proc.pid))

def setup():
    cloud.connect();s=cloud.state()
    cloud.ssh('mkdir -p /workspace/mimickit_trial')
    # Install private control and remote deadline before setup/upload work.
    with tempfile.TemporaryDirectory() as folder:
        p=Path(folder)/'private.json';write(p,dict(pod_id=s['pod_id'],deadline_unix=FAR,runpod_api_key=cloud.rp.load_api_key(),s3=cloud.credentials()))
        cloud.rp.scp(s['connection'],p,'/workspace/mimickit_trial/private.json',timeout=45)
    cloud.rp.scp(s['connection'],OUT/'runtime_control.json','/workspace/mimickit_trial/runtime_control.json',timeout=45)
    cloud.rp.scp(s['connection'],OUT/'source.zip','/workspace/mimickit_trial/source.zip',timeout=60)
    # Detach the guard explicitly. Backgrounding an entire shell && list can
    # leave SSH stdout open in its parent shell even after nohup starts.
    code='''from pathlib import Path
import json,subprocess,zipfile
r=Path('/workspace/mimickit_trial')
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
(r/'private.json').chmod(0o600)
existing=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:args=(proc/'cmdline').read_bytes().split(bytes([0]))
 except OSError:continue
 if b'pipeline/guard.py' in args or str(r/'pipeline/guard.py').encode() in args:existing.append(int(proc.name))
if not existing:
 with (r/'guard.log').open('ab',buffering=0) as log:
  p=subprocess.Popen(['python',str(r/'pipeline/guard.py')],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 existing=[p.pid]
print(json.dumps(dict(guard_pids=existing)))
'''
    print(cloud.ssh('python -c '+shlex.quote(code),timeout=30),flush=True)
    cloud.prepare_runtime_cache()
    cloud.ssh('cd /workspace/mimickit_trial; nohup bash pipeline/setup.sh > setup.log 2>&1 < /dev/null &')
    print('setup started',flush=True)

def status():
    print(cloud.ssh('cd /workspace/mimickit_trial; tail -n 8 setup.log; test ! -f runtime-cache-restored.json || cat runtime-cache-restored.json',timeout=25))

def launch(resume=None,replay_rows=8,run_kind="unperturbed",replay_interval_seconds=None):
    assert json.loads((OUT/'preflight.json').read_text())['passed']
    name=datetime.now().strftime('%Y%m%d_%H%M%S')+'_uefn_slowloco_'+run_kind+'_2048'
    args=['--name',name,'--worlds','2048','--control-mode','vel','--absolute-walk','--evaluate',
          '--equipment-omni','/workspace/mimickit_trial/prepared','--replay-rows',str(replay_rows),'--seconds',str(FAR-int(time.time())),
          '--output-interval','100']
    if replay_interval_seconds is not None:args += ['--replay-interval-seconds',str(replay_interval_seconds)]
    if resume is not None:args += ['--resume',str(resume)]
    code='''from pathlib import Path
import json,subprocess,hashlib,time
r=Path('/workspace/mimickit_trial')
assert (r/'runtime-cache-restored.json').exists()
assert not list((r/'runs').glob('*-launch.json')) if (r/'runs').exists() else True
for proc in Path('/proc').iterdir():
 if proc.name.isdigit():
  try: cmd=(proc/'cmdline').read_bytes()
  except OSError: continue
  assert str(r/'pipeline/train.py').encode() not in cmd.split(bytes([0])),'Trainer already running'
for n,h in json.loads((r/'source-inventory.json').read_text()).items():
 assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
cmd=[str(r/'venv/bin/python'),'-u',str(r/'pipeline/train.py')]+ARGS
with (r/(NAME+'.log')).open('ab',buffering=0) as log:
 p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
receipt=dict(run=NAME,pid=p.pid,command=cmd,launched_unix=time.time())
path=r/(NAME+'-launch.json');path.write_text(json.dumps(receipt))
with (r/(NAME+'-exitguard.log')).open('ab',buffering=0) as log:
 guard=subprocess.Popen([str(r/'venv/bin/python'),str(r/'pipeline/failure_stop.py'),NAME],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
receipt['exit_guard_pid']=guard.pid;path.write_text(json.dumps(receipt));print(json.dumps(receipt))
'''.replace('ARGS',repr(args)).replace('NAME',repr(name))
    receipt=json.loads(cloud.ssh('python -c '+shlex.quote(code),timeout=40))
    write(OUT/(name+'-launch.json'),receipt);write(OUT/'active_run.json',dict(run=name,name=name,pod=cloud.state()['pod_id'],state='starting',**{k:v for k,v in receipt.items() if k not in ('run','name')}))
    print(json.dumps(receipt),flush=True)

def verify():
    active=json.loads((OUT/'active_run.json').read_text());name=active['run']
    code='''from pathlib import Path
import json,time
r=Path('/workspace/mimickit_trial');d=r/'runs'/NAME
s=json.loads((d/'status.json').read_text());b=json.loads((d/'backup_status.json').read_text())
receipt=json.loads((r/(NAME+'-launch.json')).read_text())
assert s['state']=='training' and s['iteration']>=10 and time.time()-s['updated_unix']<180
assert not (d/'finished.json').exists(), 'Trainer has already finished'
assert not b['key'].endswith('_final.zip'), 'Final checkpoint indicates completed shutdown'
for key in ('pid','exit_guard_pid'):
 assert NAME.encode() in (Path('/proc')/str(receipt[key])/'cmdline').read_bytes()
assert not (d/'failure.json').exists() and not (d/'backup_errors.json').exists()
print(json.dumps(dict(status=s,backup=b,receipt=receipt)))
'''.replace('NAME',repr(name))
    live=json.loads(cloud.ssh('python -c '+shlex.quote(code),timeout=30))
    client=cloud.s3();h=hashlib.sha256();stream=client.get_object(Bucket=cloud.rp.VOLUME_ID,Key=live['backup']['key'])['Body']
    for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    stream.close();assert h.hexdigest()==live['backup']['sha256']
    write(OUT/'live-verification.json',dict(**live,verified_unix=time.time(),persistent_hash_verified=True))
    control=dict(pod_id=cloud.state()['pod_id'],hard_stop_unix=FAR,until_stopped=True,setup_watchdog=False)
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'control.json';write(path,control)
        cloud.rp.scp(cloud.state()['connection'],path,'/workspace/mimickit_trial/runtime_control.json',timeout=30)
    write(OUT/'runtime_control.json',control)
    active['state']='running_verified';write(OUT/'active_run.json',active)
    s=cloud.state();s.update(until_stopped=True,hard_stop_unix=FAR);cloud.save(s)
    print(json.dumps(dict(iteration=live['status']['iteration'],samples=live['status']['samples'],backup_verified=True,until_stopped=True)),flush=True)

def observe():
    with ServiceLock(OUT/'observer-launch.lock'):
        _observe()

def _observe():
    name=json.loads((OUT/'active_run.json').read_text())['run']
    stamp=datetime.strptime(name[:15],'%Y%m%d_%H%M%S').strftime('%Y-%m-%d_%H-%M-%S')
    source=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name)
    manifest=dict(output=str(ROOT/'Saved/MimicKit/TensorBoardRuns'),runtime_control=dict(path=str(OUT/'runtime_control.json'),pod_id=cloud.state()['pod_id']),
        runs=[dict(name=stamp+'_slow_loco_'+('disabled_curriculum' if 'disabled_curriculum' in name else 'unperturbed')+'_2048',objective='uefn_omni_absolute_walk',sources=[str(source)])])
    manifest['owner_run']=name
    path=OUT/(name+'-dashboard.json');write(path,manifest);receipts={}
    # Retire both launcher and worker, including orphaned historical observers.
    # This only touches local observers in this state directory, never the pod.
    cleanup=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(ROOT/'Labs/MimicKitTraining/stop_observers.ps1'),'-StateDir',str(OUT)],
        capture_output=True,text=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
    if cleanup.returncode:
        raise RuntimeError('Observer cleanup failed: '+cleanup.stderr)
    for kind,args in [('bridge',['--name',name]),('dashboard',[str(path)])]:
        with (OUT/(name+'-'+kind+'.log')).open('ab') as log:
            proc=subprocess.Popen([sys.executable,str(ROOT/'Labs/MimicKitTraining'/(kind+'.py'))]+args,
                stdout=log,stderr=log,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        receipts[kind]=proc.pid
    write(OUT/'observers.json',dict(run=name,**receipts));print(json.dumps(receipts))

if __name__=='__main__':globals()[sys.argv[1]]()
