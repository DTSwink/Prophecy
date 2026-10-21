"""Temporary normal get-up rehearsal and scheduled restoration; preserve latest state and deadline."""
import argparse,hashlib,json,os,shlex,subprocess,sys,zipfile
from datetime import datetime
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
from uefn_package import runtime_files,verify_package

POD='f44oylb1xk3y5o'
PLAN=OUT/'getup-rehearsal-switch.json'
OLD=json.loads(PLAN.read_text())['old_run'] if PLAN.exists() else json.loads((OUT/'active_run.json').read_text())['run']
PREFIX='mimickit/pipeline_20261014/equipment/getup-rehearsal'

def remote(code,timeout=50):
    return cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=timeout)

def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2))

def prepare():
    assert cloud.state()['pod_id']==POD
    with zipfile.ZipFile(OUT/'getup-idle-position-source.zip') as z:
        entries={n:z.read(n) for n in z.namelist()}
    allowed = {'pipeline/'+n for n in ('perturbed_omni.py',)}
    for entry, path in runtime_files(ROOT).items():
        if entries[entry] != path.read_bytes():
            assert entry in allowed, 'Unrelated runtime modification: '+entry
            entries[entry] = path.read_bytes()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml'])
    phase=options.phase
    active=json.loads((OUT/'active_run.json').read_text())
    plan=json.loads(PLAN.read_text()) if PLAN.exists() else {}
    if phase=='normal':
        assert not plan.get('normal_run'), 'Rehearsal already started'
        cfg['perturbed_motion']['getup_normal_only']=True
        cfg['idle_recovery']['random_start_fraction']=.5
    else:
        assert active['run']==plan['normal_run'], 'A newer user run superseded this switch'
        assert __import__('time').time()>=plan['switch_due_unix'], 'Scheduled switch is not due'
        cfg['perturbed_motion'].pop('getup_normal_only',None)
    plan.update(phase=phase,old_run=active['run'],pod=POD,
        hard_stop_unix=json.loads((OUT/'runtime_control.json').read_text())['hard_stop_unix'])
    PLAN.write_text(json.dumps(plan,indent=2))
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    save('getup-rehearsal-weights.json',dict(phase=phase,
        getup_normal_only=phase=='normal',normal_random_start_fraction=.5,
        perturbed_start_frame=0,other_cohorts_unchanged=True))
    path=OUT/'getup-rehearsal-source.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for n,d in entries.items():z.writestr(n,d)
    data=path.read_bytes();sha=hashlib.sha256(data).hexdigest();key=PREFIX+'/source_'+sha[:12]+'.zip'
    client=cloud.s3();client.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=data,Metadata={'sha256':sha})
    assert hashlib.sha256(client.get_object(Bucket=cloud.rp.VOLUME_ID,Key=key)['Body'].read()).hexdigest()==sha
    receipt=dict(key=key,sha256=sha,bytes=len(data),local=str(path))
    save('getup-rehearsal-source-verified.json',receipt);print(json.dumps(receipt),flush=True)

def stop():
    assert cloud.state()['pod_id']==POD
    active=json.loads((OUT/'active_run.json').read_text());assert active['run']==OLD
    code="""import json,time,subprocess,os,signal
from pathlib import Path
r=Path('/workspace/mimickit_trial');name=OLD
receipt=json.loads((r/(name+'-launch.json')).read_text());guard=receipt['exit_guard_pid']
args=(Path('/proc')/str(guard)/'cmdline').read_bytes()
assert b'failure_stop.py' in args and name.encode() in args
watch="import sys,time,json; from pathlib import Path; sys.path.insert(0,'/workspace/mimickit_trial/pipeline'); from billing_stop import stop_and_confirm; r=Path('/workspace/mimickit_trial'); end=time.time()+600; p=r/'getup_rehearsal_handoff_complete'; c=json.loads((r/'private.json').read_text()); \\nwhile time.time()<end and not p.exists():time.sleep(2)\\nif not p.exists():stop_and_confirm(c['pod_id'],c['runpod_api_key'],r/'getup_rehearsal_handoff_billing_stop.json','Perturbed correction handoff timed out')"
(r/'getup_rehearsal_handoff_complete').unlink(missing_ok=True)
with (r/'velocity-mse-handoff-guard.log').open('ab') as log:
 w=subprocess.Popen([str(r/'venv/bin/python'),'-c',watch],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
os.kill(guard,signal.SIGTERM)
(r/'runs'/name/'stop.request').touch()
print(json.dumps(dict(watchdog=w.pid,old_run=name)))
""".replace('OLD',repr(OLD))
    result=json.loads(remote(code));save('getup-rehearsal-handoff.json',result);print(json.dumps(result),flush=True)

def capture():
    code="""import json,hashlib,shutil
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial');name=OLD;p=r/'runs'/name
pid=json.loads((r/(name+'-launch.json')).read_text())['pid'];proc=Path('/proc')/str(pid)/'cmdline'
assert not proc.exists() or name.encode() not in proc.read_bytes(),'Trainer still finishing'
assert (p/'finished.json').exists(),'Final save incomplete'
b=json.loads((p/'backup_status.json').read_text());assert b['key'].endswith('_final.zip')
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
latest=json.loads(c.get_object(Bucket='aj7d2jzwuq',Key=b['key'].rsplit('/',1)[0]+'/latest_verified.json')['Body'].read());assert latest['sha256']==b['sha256']
data=(p/Path(b['key']).name).read_bytes();assert hashlib.sha256(data).hexdigest()==b['sha256']
key=PREFIX+'/preserved_'+Path(b['key']).name
c.put_object(Bucket='aj7d2jzwuq',Key=key,Body=data,Metadata={'sha256':b['sha256'],'purpose':'user-requested-preserved-before-getup-rehearsal'})
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=key)['Body'].read()).hexdigest()==b['sha256']
(r/'resume.zip').write_bytes(data)
print(json.dumps(dict(**b,preserved_key=key,finished=json.loads((p/'finished.json').read_text()))))
""".replace('OLD',repr(OLD)).replace('PREFIX',repr(PREFIX))
    receipt=json.loads(remote(code,90));save('getup-rehearsal-preserved-checkpoint.json',receipt)
    path=OUT/'preserved-checkpoints'/OLD/Path(receipt['key']).name;path.parent.mkdir(parents=True,exist_ok=True)
    cloud.s3().download_file(cloud.rp.VOLUME_ID,receipt['preserved_key'],str(path))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==receipt['sha256']
    with zipfile.ZipFile(path) as z:assert z.testzip() is None
    receipt['local']=str(path);save('getup-rehearsal-preserved-checkpoint.json',receipt)
    print(json.dumps(receipt),flush=True)

def launch():
    assert cloud.state()['pod_id']==POD
    cp=json.loads((OUT/'getup-rehearsal-preserved-checkpoint.json').read_text())
    assert hashlib.sha256(Path(cp['local']).read_bytes()).hexdigest()==cp['sha256']
    source=json.loads((OUT/'getup-rehearsal-source-verified.json').read_text())
    code="""import json,hashlib,zipfile,io
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial');c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
data=c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read();assert hashlib.sha256(data).hexdigest()==SHA
(r/'source.zip').write_bytes(data)
with zipfile.ZipFile(io.BytesIO(data)) as z:z.extractall(r)
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==CPSHA
private=json.loads((r/'private.json').read_text());private['resume_checkpoint']=CP
(r/'private.json').write_text(json.dumps(private));(r/'stop.request').unlink(missing_ok=True)
print('Source and latest checkpoint verified on owned pod')
""".replace('CPSHA',repr(cp['sha256'])).replace('KEY',repr(source['key'])).replace('SHA',repr(source['sha256'])).replace('CP',repr(dict(key=cp['preserved_key'],sha256=cp['sha256'])))
    print(remote(code,60),flush=True)
    now=datetime.now().astimezone();suffix='uefn_getup_'+json.loads(PLAN.read_text())['phase']+'_512';name=now.strftime('%Y%m%d_%H%M%S')+'_'+suffix
    remaining=int(json.loads((OUT/'runtime_control.json').read_text())['hard_stop_unix']-__import__('time').time());assert remaining>300
    args=['--name',name,'--seconds',str(remaining),'--worlds','512','--control-mode','vel','--absolute-walk',
          '--equipment-omni','/workspace/mimickit_trial/prepared','--evaluate','--output-interval','100','--replay-rows','20',
          '--resume','/workspace/mimickit_trial/resume.zip','--resume-perturbed-motion']
    subprocess.run([sys.executable,str(Path(__file__).with_name('start_training.py')),'--keep-deadline','--seconds',str(remaining),'--',*args],check=True)
    cloud.ssh('touch /workspace/mimickit_trial/getup_rehearsal_handoff_complete')
    manifest=json.loads((OUT/(OLD+'-dashboard.json')).read_text())
    manifest['runs']=[dict(name=now.strftime('%Y-%m-%d_%H-%M-%S')+'_'+suffix,objective='uefn_omni_absolute_walk',
        sources=[str(Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name))])]
    path=OUT/(name+'-dashboard.json');path.write_text(json.dumps(manifest,indent=2));observers={}
    for kind,argv in [('bridge',['--name',name]),('dashboard',[str(path)])]:
        with (OUT/(name+'-'+kind+'.log')).open('ab') as log:
            p=subprocess.Popen([sys.executable,str(Path(__file__).with_name(kind+'.py')),*argv],stdout=log,stderr=log,stdin=subprocess.DEVNULL,creationflags=0x08000000)
        observers[kind]=p.pid
    control=json.loads((OUT/'runtime_control.json').read_text())
    receipt=dict(run=name,previous_run=OLD,pod=POD,hard_stop_unix=control['hard_stop_unix'],checkpoint=cp,
        source=source,observers=observers,optimizer_settings='restored unchanged; physical-scale migration idempotent; existing KL guard retained',kl_limit=.18,curriculum_changes=json.loads((OUT/'getup-rehearsal-weights.json').read_text()))
    plan=json.loads(PLAN.read_text())
    if plan['phase']=='normal':
        plan.update(normal_run=name,normal_launched_unix=__import__('time').time(),switch_due_unix=__import__('time').time()+5400)
    else:
        plan.update(restored_run=name,restored_unix=__import__('time').time())
    PLAN.write_text(json.dumps(plan,indent=2))
    save('getup-rehearsal-launch.json',receipt);(OUT/'current-run.txt').write_text(name);print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','stop','capture','launch']);parser.add_argument('--phase',choices=['normal','mixed'],default='normal');options=parser.parse_args()
    globals()[options.action]()
