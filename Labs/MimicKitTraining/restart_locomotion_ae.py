"""Resume isolated locomotion with the existing frozen prior, 30/30 handoff."""
import hashlib,json,shlex,subprocess,sys,time,zipfile
from datetime import datetime
from pathlib import Path
import yaml
import deploy_locomotion_branch as d

OUT=d.OUT
def save(name,value):d.save(name,value)
def remote(code,timeout=50):
    return d.cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=timeout)

def prepare():
    active=json.loads((OUT/'active_run.json').read_text())
    base=json.loads((OUT/'getup-success-prepared.json').read_text())
    with zipfile.ZipFile(base['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    with zipfile.ZipFile(d.EQUIPMENT/'noise-gae-source.zip') as z:
        previous=yaml.safe_load(z.read('prepared/env_config.yaml'))['perturbed_motion']
        for n in z.namelist():
            if n.startswith('assets/motion_prior/'):entries[n]=z.read(n)
    cfg=yaml.safe_load(entries['prepared/env_config.yaml'])
    cfg['perturbed_motion'].update(mse_only=False,ae_weight=previous['ae_weight'],ae_ticks=30,blend_ticks=30,
        auxiliary='Frozen prior through tick30; linear transition to tracking MSE at tick60; existing COM2 termination/penalty')
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    # Exact live source retained: only config and restored prior assets change.
    source=OUT/'locomotion-ae30-mse30-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    with zipfile.ZipFile(source) as z:d.verify_package(z,d.ROOT)
    import torch
    from perturbed_motion import tracking_blend
    ticks=torch.tensor([0,29,30,45,59,60,120])
    torch.testing.assert_close(tracking_blend(ticks,30,30),torch.tensor([0,0,0,.5,29/30,1,1.]))
    data=source.read_bytes();sha=hashlib.sha256(data).hexdigest()
    key='mimickit/pipeline_20261014/locomotion-ae30-mse30/source_'+sha[:12]+'.zip'
    c=d.cloud.s3();c.put_object(Bucket=d.cloud.rp.VOLUME_ID,Key=key,Body=data)
    d.verified_readback(c,d.cloud.rp.VOLUME_ID,key,sha)
    plan=dict(old_run=active['run'],pod=active['pod'],source=dict(local=str(source),key=key,sha256=sha),
              ae_weight=previous['ae_weight'],ae_ticks=30,blend_ticks=30)
    save('ae30-switch',plan)
    print(json.dumps(plan),flush=True)

def stop():
    plan=json.loads((OUT/'ae30-switch.json').read_text());assert d.cloud.state()['pod_id']==plan['pod']
    code='''import json,time,subprocess,os,signal
from pathlib import Path
r=Path('/workspace/mimickit_trial');name=OLD
receipt=json.loads((r/(name+'-launch.json')).read_text());guard=receipt['exit_guard_pid']
args=(Path('/proc')/str(guard)/'cmdline').read_bytes()
assert b'failure_stop.py' in args and name.encode() in args
watch="import sys,time,json; from pathlib import Path; sys.path.insert(0,'/workspace/mimickit_trial/pipeline'); from billing_stop import stop_and_confirm; r=Path('/workspace/mimickit_trial'); end=time.time()+600; p=r/'loco_ae30_handoff_complete'; c=json.loads((r/'private.json').read_text()); \\nwhile time.time()<end and not p.exists():time.sleep(2)\\nif not p.exists():stop_and_confirm(c['pod_id'],c['runpod_api_key'],r/'loco_ae30_handoff_stop.json','AE30 handoff timed out')"
(r/'loco_ae30_handoff_complete').unlink(missing_ok=True)
with (r/'loco-ae30-guard.log').open('ab') as log:
 w=subprocess.Popen([str(r/'venv/bin/python'),'-c',watch],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
os.kill(guard,signal.SIGTERM)
(r/'runs'/name/'stop.request').touch()
print(json.dumps(dict(watchdog=w.pid,old_run=name)))
'''.replace('OLD',repr(plan['old_run']))
    result=json.loads(remote(code));save('ae30-handoff',result);print(result,flush=True)

def capture():
    plan=json.loads((OUT/'ae30-switch.json').read_text())
    code='''from pathlib import Path
import json,hashlib,time,shutil
r=Path('/workspace/mimickit_trial');p=r/'runs'/OLD
for _ in range(8):
 if (p/'finished.json').exists():break
 time.sleep(5)
assert (p/'finished.json').exists(),'Trainer still finishing'
b=json.loads((p/'backup_status.json').read_text());assert b['key'].endswith('_final.zip')
cp=p/Path(b['key']).name;assert hashlib.sha256(cp.read_bytes()).hexdigest()==b['sha256']
shutil.copyfile(cp,r/'resume.zip')
print(json.dumps(dict(**b,finished=json.loads((p/'finished.json').read_text()))))
'''.replace('OLD',repr(plan['old_run']))
    cp=json.loads(remote(code));c=d.cloud.s3()
    d.verified_readback(c,d.cloud.rp.VOLUME_ID,cp['key'],cp['sha256'])
    path=OUT/'preserved-latest'/plan['old_run']/Path(cp['key']).name;path.parent.mkdir(parents=True,exist_ok=True)
    c.download_file(d.cloud.rp.VOLUME_ID,cp['key'],str(path))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==cp['sha256']
    with zipfile.ZipFile(path) as z:assert z.testzip() is None
    cp.update(local=str(path),preserved_key=cp['key']);plan['checkpoint']=cp
    save('ae30-switch',plan);print(json.dumps(cp),flush=True)

def launch():
    plan=json.loads((OUT/'ae30-switch.json').read_text());source=plan['source'];cp=plan['checkpoint']
    code='''import json,hashlib,zipfile,io
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial');p=json.loads((r/'private.json').read_text())
c=boto3.client('s3',**p['s3']);data=c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()
assert hashlib.sha256(data).hexdigest()==SHA
(r/'source.zip').write_bytes(data)
with zipfile.ZipFile(io.BytesIO(data)) as z:z.extractall(r)
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==CPSHA
p['resume_checkpoint']=CP
(r/'private.json').write_text(json.dumps(p))
(r/'stop.request').unlink(missing_ok=True)
print('Source and final checkpoint verified')
'''.replace('CPSHA',repr(cp['sha256'])).replace('KEY',repr(source['key'])).replace('SHA',repr(source['sha256'])).replace('CP',repr(dict(key=cp['key'],sha256=cp['sha256'])))
    print(remote(code),flush=True)
    now=datetime.now().astimezone();suffix='uefn_locomotion_ae30_mse30_yaw180_512';name=now.strftime('%Y%m%d_%H%M%S')+'_'+suffix
    from extend_runtime import extend
    extend(until_stopped=True)
    args=['--name',name,'--seconds','86400','--worlds','512','--control-mode','vel','--absolute-walk',
          '--equipment-omni','/workspace/mimickit_trial/prepared','--evaluate','--output-interval','100','--replay-rows','20',
          '--resume','/workspace/mimickit_trial/resume.zip','--actor-lr','1.125e-6','--resume-perturbed-motion']
    subprocess.run([sys.executable,str(Path(__file__).with_name('start_training.py')),'--keep-deadline',
        '--source-package',source['local'],'--source-sha256',source['sha256'],'--seconds','86400','--',*args],check=True)
    manifest=json.loads((OUT/(plan['old_run']+'-dashboard.json')).read_text())
    manifest['runs']=[dict(name=now.strftime('%Y-%m-%d_%H-%M-%S')+'_'+suffix,objective='uefn_omni_absolute_walk',training_outcomes=True,
        sources=[str(Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name))])]
    path=OUT/(name+'-dashboard.json');path.write_text(json.dumps(manifest,indent=2));observers={}
    for kind,argv in [('bridge',['--name',name]),('dashboard',[str(path)])]:
        with (OUT/(name+'-'+kind+'.log')).open('ab') as log:
            p=subprocess.Popen([sys.executable,str(Path(__file__).with_name(kind+'.py')),*argv],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
        observers[kind]=p.pid
    (OUT/'current-run.txt').write_text(name)
    save('ae30-launch',dict(run=name,pod=plan['pod'],observers=observers,prepared=plan))
    base=json.loads((OUT/'getup-success-prepared.json').read_text());base.update(source=source,checkpoint=cp,run_suffix=suffix)
    save('getup-success-prepared',base)
    print(json.dumps(dict(run=name,observers=observers)),flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
