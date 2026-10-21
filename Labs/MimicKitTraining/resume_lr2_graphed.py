"""Authorized double actual actor LR plus verified observation optimization; latest checkpoint preserved."""
import argparse,hashlib,json,os,shlex,subprocess,sys,zipfile
from datetime import datetime
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
from uefn_package import runtime_files,verify_package

PLAN=OUT/'lr2-graphed-switch.json'
POD=json.loads(PLAN.read_text()).get('pod','f44oylb1xk3y5o') if PLAN.exists() else 'f44oylb1xk3y5o'
OLD=json.loads(PLAN.read_text())['old_run'] if PLAN.exists() else json.loads((OUT/'active_run.json').read_text())['run']
PREFIX='mimickit/pipeline_20261014/equipment/lr2-graphed'

def remote(code,timeout=50):
    return cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=timeout)

def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2))

def prepare():
    assert cloud.state()['pod_id']==POD
    base=OUT/'graphed-observations-source.zip'
    with zipfile.ZipFile(base) as z: entries={n:z.read(n) for n in z.namelist()}
    for f in ['perturbed_omni.py','batched_joint_conversion.py','device_quaternion.py','graphed_observations.py','uefn_package.py','train.py','bridge.py','replay.py']:
        entries['pipeline/'+f]=(ROOT/'Labs/MimicKitTraining'/f).read_bytes()
    # Environment and agent settings stay byte-identical; LR override follows restore.
    with zipfile.ZipFile(OUT/'loco-failure-penalty-source.zip') as previous:
        for name in ['prepared/env_config.yaml','prepared/engine_config.yaml','prepared/agent_config.yaml']:
            assert entries[name]==previous.read(name), 'Unexpected configuration change: '+name
    save('lr2-graphed-weights.json',dict(change='Double actual restored actor LR; deploy verified device quaternion and graphed physical observations; retain KL guard and all objectives'))
    path=OUT/'lr2-graphed-source.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for n,d in entries.items():z.writestr(n,d)
    with zipfile.ZipFile(path) as z:verify_package(z,ROOT)
    data=path.read_bytes();sha=hashlib.sha256(data).hexdigest();key=PREFIX+'/source_'+sha[:12]+'.zip'
    client=cloud.s3();client.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=data,Metadata={'sha256':sha})
    assert hashlib.sha256(client.get_object(Bucket=cloud.rp.VOLUME_ID,Key=key)['Body'].read()).hexdigest()==sha
    save('lr2-graphed-source-verified.json',dict(key=key,sha256=sha,bytes=len(data),local=str(path)))
    print('Source verified',flush=True)


def stop():
    assert cloud.state()['pod_id']==POD
    active=json.loads((OUT/'active_run.json').read_text());assert active['run']==OLD
    code="""import json,time,subprocess,os,signal
from pathlib import Path
r=Path('/workspace/mimickit_trial');name=OLD
receipt=json.loads((r/(name+'-launch.json')).read_text());guard=receipt['exit_guard_pid']
args=(Path('/proc')/str(guard)/'cmdline').read_bytes()
assert b'failure_stop.py' in args and name.encode() in args
watch="import sys,time,json; from pathlib import Path; sys.path.insert(0,'/workspace/mimickit_trial/pipeline'); from billing_stop import stop_and_confirm; r=Path('/workspace/mimickit_trial'); end=time.time()+600; p=r/'lr2_graphed_handoff_complete'; c=json.loads((r/'private.json').read_text()); \\nwhile time.time()<end and not p.exists():time.sleep(2)\\nif not p.exists():stop_and_confirm(c['pod_id'],c['runpod_api_key'],r/'lr2_graphed_handoff_billing_stop.json','Perturbed correction handoff timed out')"
(r/'lr2_graphed_handoff_complete').unlink(missing_ok=True)
with (r/'velocity-mse-handoff-guard.log').open('ab') as log:
 w=subprocess.Popen([str(r/'venv/bin/python'),'-c',watch],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
os.kill(guard,signal.SIGTERM)
(r/'runs'/name/'stop.request').touch()
print(json.dumps(dict(watchdog=w.pid,old_run=name)))
""".replace('OLD',repr(OLD))
    result=json.loads(remote(code));save('lr2-graphed-handoff.json',result);print(json.dumps(result),flush=True)

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
c.put_object(Bucket='aj7d2jzwuq',Key=key,Body=data,Metadata={'sha256':b['sha256'],'purpose':'user-requested-preserved-before-lr2-graphed'})
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=key)['Body'].read()).hexdigest()==b['sha256']
(r/'resume.zip').write_bytes(data)
print(json.dumps(dict(**b,preserved_key=key,finished=json.loads((p/'finished.json').read_text()))))
""".replace('OLD',repr(OLD)).replace('PREFIX',repr(PREFIX))
    receipt=json.loads(remote(code,90));save('lr2-graphed-preserved-checkpoint.json',receipt)
    path=OUT/'preserved-checkpoints'/OLD/Path(receipt['key']).name;path.parent.mkdir(parents=True,exist_ok=True)
    cloud.s3().download_file(cloud.rp.VOLUME_ID,receipt['preserved_key'],str(path))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==receipt['sha256']
    with zipfile.ZipFile(path) as z:assert z.testzip() is None
    receipt['local']=str(path);save('lr2-graphed-preserved-checkpoint.json',receipt)
    import torch,io
    with zipfile.ZipFile(path) as archive:
        state=torch.load(io.BytesIO(archive.read('resume_state.pt')),map_location='cpu',weights_only=False)
    rates=[float(g['lr']) for g in state['actor_optimizer']['param_groups']]
    assert rates and len(set(rates))==1
    receipt.update(previous_actor_lr=rates[0],requested_actor_lr=2*rates[0])
    save('lr2-graphed-preserved-checkpoint.json',receipt)
    print(json.dumps(receipt),flush=True)

def launch():
    assert cloud.state()['pod_id']==POD
    cp=json.loads((OUT/'lr2-graphed-preserved-checkpoint.json').read_text())
    assert hashlib.sha256(Path(cp['local']).read_bytes()).hexdigest()==cp['sha256']
    source=json.loads((OUT/'lr2-graphed-source-verified.json').read_text())
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
    now=datetime.now().astimezone();stage=json.loads(PLAN.read_text())['pending_stage'];suffix='uefn_lr2_graphed_linear_512';name=now.strftime('%Y%m%d_%H%M%S')+'_'+suffix
    control=json.loads((OUT/'runtime_control.json').read_text())
    assert control.get('until_stopped') and control['pod_id']==POD
    remaining=86400  # Live until_stopped control, read by trainer, overrides this fallback.
    args=['--name',name,'--seconds',str(remaining),'--worlds','512','--control-mode','vel','--absolute-walk',
          '--equipment-omni','/workspace/mimickit_trial/prepared','--evaluate','--output-interval','100','--replay-rows','20',
          '--resume','/workspace/mimickit_trial/resume.zip','--actor-lr',str(cp['requested_actor_lr']),
          '--resume-perturbed-motion' if stage=='perturbed' else '--resume-recovery-curriculum']
    subprocess.run([sys.executable,str(Path(__file__).with_name('start_training.py')),'--keep-deadline','--seconds',str(remaining),'--',*args],check=True)
    cloud.ssh('touch /workspace/mimickit_trial/lr2_graphed_handoff_complete')
    manifest=json.loads((OUT/(OLD+'-dashboard.json')).read_text())
    manifest['runtime_control']['pod_id']=POD
    manifest['runs']=[dict(name=now.strftime('%Y-%m-%d_%H-%M-%S')+'_'+suffix,objective='uefn_omni_absolute_walk',training_outcomes=True,
        sources=[str(Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name))])]
    path=OUT/(name+'-dashboard.json');path.write_text(json.dumps(manifest,indent=2));observers={}
    for kind,argv in [('bridge',['--name',name]),('dashboard',[str(path)])]:
        with (OUT/(name+'-'+kind+'.log')).open('ab') as log:
            p=subprocess.Popen([sys.executable,str(Path(__file__).with_name(kind+'.py')),*argv],stdout=log,stderr=log,stdin=subprocess.DEVNULL,creationflags=0x08000000)
        observers[kind]=p.pid
    control=json.loads((OUT/'runtime_control.json').read_text())
    receipt=dict(run=name,previous_run=OLD,pod=POD,hard_stop_unix=control['hard_stop_unix'],checkpoint=cp,
        source=source,observers=observers,optimizer_settings='Adam state retained; actual restored actor LR doubled explicitly; existing KL guard retained',kl_limit=.18,curriculum_changes=json.loads((OUT/'lr2-graphed-weights.json').read_text()))
    plan=json.loads(PLAN.read_text())
    # Keep the established half-hour schedule through the short checkpoint
    # handoff; moving eligibility later can otherwise skip the next wake.
    next_check=max(__import__('time').time(),plan.get('next_check_unix',__import__('time').time()+1800))
    plan.update(stage=stage,active_run=name,stage_started_unix=__import__('time').time(),
                next_check_unix=next_check,next_stage=None)
    plan.pop('settle_until_unix',None)
    PLAN.write_text(json.dumps(plan,indent=2))
    save('lr2-graphed-launch.json',receipt);(OUT/'current-run.txt').write_text(name);print(json.dumps(receipt),flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("action",choices=["prepare","stop","capture","launch"]);args=parser.parse_args();globals()[args.action]()
