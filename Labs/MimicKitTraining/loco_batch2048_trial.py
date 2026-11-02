"""Scoped 15-minute 2048-world trial of the unchanged October24 source."""
import json, os, subprocess, sys, time
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MAIN=ROOT/'Saved/MimicKitLocomotion'
OUT=ROOT/'Saved/MimicKitLocomotionSweeps/20261024_batch2048'
OUT.mkdir(parents=True,exist_ok=True)
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
import deploy_locomotion_branch as d
d.OUT=OUT
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
assert cloud.OUT==OUT and d.OUT!=MAIN

def prepare():
    p=json.loads((MAIN/'getup-success-prepared.json').read_text())
    p.update(worlds=2048,until_stopped=False,run_suffix='uefn_locomotion_batch2048_trial')
    d.save('getup-success-prepared',p)
    d.save('comparison',dict(baseline=json.loads((MAIN/'active_run.json').read_text()),
        checkpoint=p['checkpoint'],source=p['source'],training_seconds=900,
        changed_setting='worlds 1024 -> 2048; all other training settings retained',
        comparison='First 900 seconds of each training loop, including ordinary evaluation/checkpoint overhead; full-batch outcomes, not small replay sample. One trial, provisional evidence.'))

def launch():
    p=json.loads((OUT/'getup-success-prepared.json').read_text())
    from extend_runtime import extend
    extend(time.time()+1350)
    name=datetime.now().astimezone().strftime('%Y%m%d_%H%M%S')+'_'+p['run_suffix']
    argv=['--name',name,'--seconds','900','--worlds','2048','--control-mode','vel',
        '--absolute-walk','--equipment-omni','/workspace/mimickit_trial/prepared',
        '--evaluate','--output-interval','100','--replay-rows','20',
        '--resume','/workspace/mimickit_trial/resume.zip','--actor-lr','1.125e-6','--resume-perturbed-motion']
    subprocess.run([sys.executable,str(Path(__file__).with_name('start_training.py')),
        '--keep-deadline','--seconds','900','--source-package',p['source']['local'],
        '--source-sha256',p['source']['sha256'],'--',*argv],check=True)
    # The fixed ceiling covers warmup. Once the loop reports its start, arm its
    # exact 900-second stop plus the trainer's existing165-second save reserve.
    code="""import subprocess
from pathlib import Path
r=Path('/workspace/mimickit_trial')
with (r/'trial-deadline.log').open('ab') as log:
 subprocess.Popen(['python',str(r/'pipeline/guard.py')],cwd=r,stdout=log,stderr=log,start_new_session=True)
print('Remote billing deadline active')
"""
    print(d.remote(code))

def inspect():
    name=json.loads((OUT/'active_run.json').read_text())['run']
    code="""from pathlib import Path
import json,time
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
data={f:json.loads((p/f).read_text()) for f in ['status.json','backup_status.json','finished.json','backup_errors.json'] if (p/f).exists()}
if not data: data['log_tail']=(r/(NAME+'.log')).read_text()[-1500:]
print(json.dumps(data))
""".replace('NAME',repr(name))
    x=json.loads(d.remote(code));d.save('inspection',x)
    if x.get('status.json') and not (OUT/'timing-armed.json').exists():
        s=x['status.json'];start=s['updated_unix']-s['elapsed_seconds']
        from extend_runtime import extend
        extend(start+900+165)
        d.save('timing-armed',dict(start=start,training_end=start+900,billing_stop=start+1065))
    if x.get('backup_status.json') and x.get('status.json',{}).get('iteration',0)>167206:
        (OUT/'setup-verified').write_text('Advancing with verified persistent backup; bounded remote guard active')
    for key,val in x.items():
        if key=='status.json':val={k:val.get(k) for k in ['state','iteration','samples','training_transitions_per_second','elapsed_seconds']}
        print(key,json.dumps(val))

def fetch(baseline=False):
    scope=MAIN if baseline else OUT
    active=json.loads((scope/'active_run.json').read_text())
    prior=cloud.OUT
    cloud.OUT=scope
    code="""from pathlib import Path
import json
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
p=Path('/workspace/mimickit_trial/runs')/NAME
s=json.loads((p/'status.json').read_text())
tags={}
for f in p.rglob('events.*'):
 e=EventAccumulator(str(f),size_guidance={'scalars':0});e.Reload()
 for tag in e.Tags()['scalars']:
  if tag.startswith(('perturbed_','0_Main/','Misc/Policy_Kl','Misc/Actor_Full_Rollback','loss/total','1_Info/Samples_Per_Second')):
   tags.setdefault(tag,[]).extend([[v.wall_time,v.step,v.value] for v in e.Scalars(tag)])
print(json.dumps(dict(status=s,start=s['updated_unix']-s['elapsed_seconds'],scalars=tags,
 backup=json.loads((p/'backup_status.json').read_text()) if (p/'backup_status.json').exists() else None,
 finished=json.loads((p/'finished.json').read_text()) if (p/'finished.json').exists() else None)))
""".replace('NAME',repr(active['run']))
    try:
        import shlex
        data=json.loads(cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=45))
    finally:cloud.OUT=prior
    d.save('baseline-data' if baseline else 'trial-data',data)
    print(json.dumps(dict(run=active['run'],points=sum(len(v) for v in data['scalars'].values()),
        iteration=data['status']['iteration'],elapsed=data['status']['elapsed_seconds'],finished=bool(data['finished']))))

def fetch_baseline():fetch(True)

def restart_ready():
    import loco_sweep_cloud as sweep
    sweep.OUT=OUT;os.environ['MIMICKIT_STATE_DIR']=str(OUT)
    pod=cloud.state()['pod_id']
    assert cloud.rp.request_json('GET','/pods/'+pod)['desiredStatus']=='EXITED'
    cloud.rp.request_json('POST','/pods/'+pod+'/start')
    sweep.protect_setup()
    print('Owned trial pod restarted with fresh bounded setup guard',flush=True)
    cloud.connect()
    # Remove only the known dangling symlink, never its target or a directory.
    print(d.remote("""from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'venv'
if p.is_symlink():
 assert str(p.readlink())=='/opt/mimickit-runtime/venv'
 p.unlink()
for name in ['runtime-cache-restored.json','billing_stopped.json']:
 (r/name).unlink(missing_ok=True)
print('Cleared stale runtime symlink and receipts')
"""),flush=True)
    d.runtime()
    end=time.time()+240
    while time.time()<end:
        ready=d.remote("from pathlib import Path;r=Path('/workspace/mimickit_trial');print(int((r/'runtime-cache-restored.json').exists() and (r/'venv/bin/python').exists()))").strip()
        if ready=='1':break
        time.sleep(5)
    else:raise RuntimeError('Runtime cache restore timeout')
    print('Complete runtime and kernel cache restored',flush=True)
    (OUT/'timing-armed.json').unlink(missing_ok=True)
    launch()
    end=time.time()+240
    while time.time()<end:
        inspect()
        if (OUT/'setup-verified').exists():break
        time.sleep(12)
    else:raise RuntimeError('Trial did not advance/verify backup during bounded startup')
    print('Trial advancing; exact15minute timer armed; setup guard released',flush=True)

def collect_finished():
    import hashlib,zipfile,io
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    pod=cloud.state()['pod_id'];state=cloud.rp.request_json('GET','/pods/'+pod)
    assert state['desiredStatus']=='EXITED','Trial has not stopped yet'
    name=json.loads((OUT/'active_run.json').read_text())['run']
    prefix='mimickit/pipeline_20261014/runs/'+name+'/'
    c=cloud.s3();bucket=cloud.rp.VOLUME_ID
    cp=json.loads(c.get_object(Bucket=bucket,Key=prefix+'latest_verified.json')['Body'].read())
    assert cp['key'].startswith(prefix) and cp['key'].endswith('_final.zip')
    local=OUT/Path(cp['key']).name;c.download_file(bucket,cp['key'],str(local))
    assert hashlib.sha256(local.read_bytes()).hexdigest()==cp['sha256']
    with zipfile.ZipFile(local) as z:assert z.testzip() is None
    cp['local']=str(local);d.save('trial-final-checkpoint',cp)
    keys=[v['Key'] for v in c.list_objects_v2(Bucket=bucket,Prefix=prefix+'exit_evidence_').get('Contents',[])]
    assert len(keys)==1,keys
    raw=c.get_object(Bucket=bucket,Key=keys[0])['Body'].read()
    assert hashlib.sha256(raw).hexdigest()[:12] in keys[0]
    (OUT/'completed-exit-evidence.zip').write_bytes(raw)
    evidence=OUT/'completed-evidence';evidence.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for name in z.namelist():
            assert '/' not in name and '\\' not in name
            (evidence/name).write_bytes(z.read(name))
    s=json.loads((evidence/'status.json').read_text())
    finished=json.loads((evidence/'finished.json').read_text())
    tags={}
    for f in evidence.glob('events.*'):
        e=EventAccumulator(str(f),size_guidance={'scalars':0});e.Reload()
        for tag in e.Tags()['scalars']:
            if tag.startswith(('perturbed_','0_Main/','Misc/Policy_Kl','Misc/Actor_Full_Rollback','loss/total','1_Info/Samples_Per_Second')):
                tags.setdefault(tag,[]).extend([[v.wall_time,v.step,v.value] for v in e.Scalars(tag)])
    d.save('trial-data',dict(status=s,start=s['updated_unix']-s['elapsed_seconds'],scalars=tags,backup=cp,finished=finished))
    d.save('completed',dict(pod=pod,pod_status='EXITED',finished=finished,checkpoint=cp,evidence_key=keys[0],collected_unix=time.time()))
    print(json.dumps(dict(pod=pod,status='EXITED',finished=finished,checkpoint=cp['local'])))

if __name__=='__main__':
    action=sys.argv[1]
    if action in ['allocate','provision','runtime']:getattr(d,action)()
    else:globals()[action]()
