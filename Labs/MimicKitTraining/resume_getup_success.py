"""Resume the pre-stall checkpoint with explicitly credited get-up success."""
import hashlib,json,os,shlex,subprocess,sys,tempfile,time,zipfile
from datetime import datetime
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
from backup import verified_readback
from botocore.config import Config
import boto3
from uefn_package import verify_package

def remote(code,timeout=45):
    return cloud.ssh('python -c '+shlex.quote(code),timeout=timeout)
def prepare():
    cp=json.loads((OUT/'lr2-graphed-preserved-checkpoint.json').read_text())
    data=Path(cp['local']).read_bytes();assert hashlib.sha256(data).hexdigest()==cp['sha256']
    c=boto3.client('s3',**cloud.credentials(),config=Config(connect_timeout=15,read_timeout=90,retries={'total_max_attempts':1}))
    print('Verifying preserved checkpoint in persistent storage',flush=True)
    verified_readback(c,cloud.rp.VOLUME_ID,cp['preserved_key'],cp['sha256'])
    print('Checkpoint persistent readback verified',flush=True)
    with zipfile.ZipFile(OUT/'getup-skew-source.zip') as z:entries={n:z.read(n) for n in z.namelist()}
    for f in ['perturbed_omni.py','omni_policy.py','observe.py','replay.py','backup.py']:
        entries['pipeline/'+f]=(ROOT/'Labs/MimicKitTraining'/f).read_bytes()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml'])
    cfg['perturbed_motion'].update(getup_success_value=100.,getup_success_discount=.99)
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    path=OUT/'getup-success-source.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for n,d in entries.items():z.writestr(n,d)
    with zipfile.ZipFile(path) as z:verify_package(z,ROOT)
    data=path.read_bytes();sha=hashlib.sha256(data).hexdigest()
    key='mimickit/pipeline_20261014/equipment/getup-success/source_'+sha[:12]+'.zip'
    c.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=data,Metadata={'sha256':sha})
    print('Updated source uploaded; verifying readback',flush=True)
    verified_readback(c,cloud.rp.VOLUME_ID,key,sha)
    receipt=dict(checkpoint=cp,source=dict(local=str(path),key=key,sha256=sha),verified_unix=time.time())
    (OUT/'getup-success-prepared.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)
def start():
    assert (OUT/'getup-success-prepared.json').exists()
    pod=cloud.state()['pod_id']
    assert pod in {'ka68jrougesuit','iiprikebnm51jl','9r63p3vlvogqz5','rovwuwstkm0s7r','new5546ihvxeax'}, 'Reconcile owned pod before restart'
    p=cloud.rp.request_json('GET','/pods/'+pod);assert float(p['costPerHr'])<=.59
    assert p['desiredStatus']=='EXITED'
    cloud.rp.request_json('POST','/pods/'+pod+'/start')
    marker=OUT/'getup-success-launched';marker.unlink(missing_ok=True)
    guardcode=f"""import sys,time,os
from pathlib import Path
sys.path.insert(0,{str(ROOT/'Labs/MimicKitTraining')!r})
import cloud
from billing_stop import stop_and_confirm
end=time.time()+600
while time.time()<end and not Path({str(marker)!r}).exists():time.sleep(2)
if not Path({str(marker)!r}).exists():stop_and_confirm({pod!r},cloud.rp.load_api_key(),Path({str(OUT/'getup-success-setup-timeout.json')!r}),'Success-value setup exceeded ten minutes')
"""
    with (OUT/'getup-success-setup-guard.log').open('ab') as log:
        g=subprocess.Popen([sys.executable,'-c',guardcode],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
    print('setup guard',g.pid,flush=True)
    cloud.connect()
    if '--sdk-restore' in sys.argv:
        return
    ready=remote("from pathlib import Path; p=Path('/workspace/mimickit_trial/venv'); p.unlink() if p.is_symlink() and not p.exists() else None; print(int((p/'bin/python').exists()))").strip()
    if ready!='1':
        cloud.prepare_runtime_cache()
        print(remote("""import subprocess
from pathlib import Path
r=Path('/workspace/mimickit_trial')
with (r/'success-runtime.log').open('ab') as log:
 p=subprocess.Popen(['timeout','180','python','pipeline/runtime_cache.py','restore'],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(p.pid)
"""),flush=True)
def replace():
    plan=json.loads((OUT/'getup-success-prepared.json').read_text())
    old=cloud.state();assert old['pod_id'] in {'ka68jrougesuit','iiprikebnm51jl','9r63p3vlvogqz5','rovwuwstkm0s7r','new5546ihvxeax','w9aq90rzkg1d0g','90v1fafvq5uudn'}
    assert cloud.rp.request_json('GET','/pods/'+old['pod_id'])['desiredStatus']=='EXITED'
    retained=OUT/'retained-pods'/old['pod_id'];retained.mkdir(parents=True,exist_ok=True)
    moved=[]
    for name in ['pod.json','runtime_control.json','active_run.json']:
        src=OUT/name;dest=retained/(str(int(time.time()))+'-'+name)
        assert src.resolve().is_relative_to(OUT.resolve()) and dest.resolve().is_relative_to(OUT.resolve())
        if src.exists():src.replace(dest);moved.append((src,dest))
    try:
        cloud.allocate('NVIDIA L4',.59,'SECURE',seconds=600,name='mimickit-success-recovery-'+str(int(time.time())))
    except Exception:
        if not (OUT/'pod.json').exists():
            for src,dest in moved:dest.replace(src)
        raise
    pod=cloud.state()['pod_id']
    control=dict(pod_id=pod,hard_stop_unix=time.time()+600,until_stopped=False,updated_unix=time.time())
    (OUT/'runtime_control.json').write_text(json.dumps(control))
    with (OUT/'getup-success-replacement-guard.log').open('ab') as log:
        g=subprocess.Popen([sys.executable,str(Path(__file__).with_name('local_guard.py'))],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
    (OUT/'getup-success-replacement.json').write_text(json.dumps(dict(old=old['pod_id'],pod=pod,guard_pid=g.pid,setup_deadline=control['hard_stop_unix'])))
    print('Replacement allocated; bounded setup guard active',flush=True)
    cloud.connect();r='/workspace/mimickit_trial';con=cloud.state()['connection']
    cloud.ssh('mkdir -p '+r)
    if '--sdk-restore' in sys.argv:
        return
    cloud.rp.scp(con,Path(plan['source']['local']),r+'/source.zip',timeout=60)
    remote("import zipfile;zipfile.ZipFile('/workspace/mimickit_trial/source.zip').extractall('/workspace/mimickit_trial')")
    private=dict(pod_id=pod,deadline_unix=control['hard_stop_unix']-120,runpod_api_key=cloud.rp.load_api_key(),
        s3=cloud.credentials(),resume_checkpoint=dict(key=plan['checkpoint']['preserved_key'],sha256=plan['checkpoint']['sha256']))
    with tempfile.TemporaryDirectory() as directory:
        p=Path(directory)/'private.json';p.write_text(json.dumps(private))
        cloud.rp.scp(con,p,r+'/private.json',timeout=30)
    cloud.rp.scp(con,OUT/'runtime_control.json',r+'/runtime_control.json',timeout=30)
    remote("""import subprocess,os
from pathlib import Path
r=Path('/workspace/mimickit_trial');os.chmod(r/'private.json',0o600)
with (r/'success-remote-guard.log').open('ab') as log:
 subprocess.Popen(['python','pipeline/guard.py'],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
""")
    cloud.prepare_runtime_cache()
    print(remote("""import subprocess
from pathlib import Path
r=Path('/workspace/mimickit_trial')
with (r/'success-runtime.log').open('ab') as log:
 p=subprocess.Popen(['timeout','240','python','pipeline/runtime_cache.py','restore'],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print('Runtime restore PID',p.pid)
"""),flush=True)
def provision():
    """Continue an allocated replacement using cloud-to-cloud artifact transfer."""
    plan=json.loads((OUT/'getup-success-prepared.json').read_text())
    pod=cloud.state()['pod_id'];con=cloud.state()['connection'];r='/workspace/mimickit_trial'
    control=json.loads((OUT/'runtime_control.json').read_text())
    private=dict(pod_id=pod,deadline_unix=control['hard_stop_unix']-120,runpod_api_key=cloud.rp.load_api_key(),
        s3=cloud.credentials(),resume_checkpoint=dict(key=plan['checkpoint']['preserved_key'],sha256=plan['checkpoint']['sha256']))
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    from botocore.credentials import Credentials
    cfg=private['s3'];hint={}
    for label,item in [('source',plan['source']),('resume',dict(key=plan['checkpoint']['preserved_key'],sha256=plan['checkpoint']['sha256']))]:
        url=cfg['endpoint_url']+'/'+cloud.rp.VOLUME_ID+'/'+item['key']
        req=AWSRequest(method='GET',url=url,headers={'User-Agent':'MimicKit-runtime-cache/1.0','X-Amz-Content-SHA256':hashlib.sha256(b'').hexdigest()})
        SigV4Auth(Credentials(cfg['aws_access_key_id'],cfg['aws_secret_access_key']),'s3',cfg['region_name']).add_auth(req)
        hint[label]=dict(url=url,headers=dict(req.headers),sha256=item['sha256'])
    with tempfile.TemporaryDirectory() as directory:
        for filename,value in [('private.json',private),('success-download.json',hint)]:
            path=Path(directory)/filename;path.write_text(json.dumps(value))
            cloud.rp.scp(con,path,r+'/'+filename,timeout=30)
    cloud.rp.scp(con,OUT/'runtime_control.json',r+'/runtime_control.json',timeout=30)
    script="""import json,urllib.request,hashlib,zipfile,os
from pathlib import Path
r=Path('/workspace/mimickit_trial');os.chmod(r/'private.json',0o600);os.chmod(r/'success-download.json',0o600)
hint=json.loads((r/'success-download.json').read_text())
for label,item in hint.items():
 p=r/(label+'.download')
 with urllib.request.urlopen(urllib.request.Request(item['url'],headers=item['headers']),timeout=90) as src,p.open('wb') as dest:
  while True:
   b=src.read(1024*1024)
   if not b:break
   dest.write(b)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
 p.replace(r/(label+'.zip'))
 print(label+' verified',flush=True)
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
(r/'success-download-ready').touch()
"""
    with tempfile.TemporaryDirectory() as directory:
        p=Path(directory)/'download.py';p.write_text(script);cloud.rp.scp(con,p,r+'/success-download.py',timeout=30)
    print(remote("""import subprocess
from pathlib import Path
r=Path('/workspace/mimickit_trial')
with (r/'success-download.log').open('ab') as log:
 p=subprocess.Popen(['timeout','240','python','success-download.py'],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(p.pid)
"""),flush=True)
def runtime():
    cloud.prepare_runtime_cache()
    print(remote("""import subprocess
from pathlib import Path
r=Path('/workspace/mimickit_trial');assert (r/'success-download-ready').exists()
with (r/'success-runtime.log').open('ab') as log:
 p=subprocess.Popen(['timeout','240','python','pipeline/runtime_cache.py','restore'],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(p.pid)
"""),flush=True)
def launch():
    plan=json.loads((OUT/'getup-success-prepared.json').read_text());cp=plan['checkpoint']
    r='/workspace/mimickit_trial';con=cloud.state()['connection']
    # provision() downloaded and hash-checked these directly from persistent storage.
    print(remote("""import zipfile,hashlib,json
from pathlib import Path
r=Path('/workspace/mimickit_trial')
assert (r/'venv/bin/python').exists()
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==SHA
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
p=json.loads((r/'private.json').read_text());p['resume_checkpoint']=CP
(r/'private.json').write_text(json.dumps(p));(r/'stop.request').unlink(missing_ok=True)
print('Checkpoint and runtime ready')
""".replace('SHA',repr(cp['sha256'])).replace('CP',repr(dict(key=cp['preserved_key'],sha256=cp['sha256'])))),flush=True)
    now=datetime.now().astimezone()
    suffix=plan.get('run_suffix','uefn_getup_success_value_512')
    name=now.strftime('%Y%m%d_%H%M%S')+'_'+suffix
    control=json.loads((OUT/'runtime_control.json').read_text())
    if not control.get('until_stopped'):
        from extend_runtime import extend
        extend(until_stopped=True)
    args=['--name',name,'--seconds','86400','--worlds',str(plan.get('worlds',512)),'--control-mode','vel','--absolute-walk',
          '--equipment-omni',r+'/prepared','--evaluate','--output-interval','100','--replay-rows','20',
          '--resume',r+'/resume.zip','--actor-lr','1.125e-6','--resume-perturbed-motion']
    overrides=plan.get('training_overrides',{})
    if overrides.get('resume_position_leeway'):
        args.append('--resume-position-leeway')
    for key,flag in [('action_noise','--action-noise'),('gae_lambda','--gae-lambda')]:
        if key in overrides:args.extend([flag,str(overrides[key])])
    subprocess.run([sys.executable,str(Path(__file__).with_name('start_training.py')),'--keep-deadline','--seconds','86400',
        '--source-package',plan['source']['local'],'--source-sha256',plan['source']['sha256'],'--',*args],check=True)
    old='20261020_094614_uefn_getup_skew_linear_512'
    manifest=json.loads((OUT/(old+'-dashboard.json')).read_text())
    manifest['runtime_control']['pod_id']=cloud.state()['pod_id']
    manifest['runs']=[dict(name=now.strftime('%Y-%m-%d_%H-%M-%S')+'_'+suffix,
        objective='uefn_omni_absolute_walk',training_outcomes=True,
        sources=[str(Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name))])]
    path=OUT/(name+'-dashboard.json');path.write_text(json.dumps(manifest,indent=2));pids={}
    for kind,argv in [('bridge',['--name',name]),('dashboard',[str(path)])]:
        with (OUT/(name+'-'+kind+'.log')).open('ab') as log:
            proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name(kind+'.py')),*argv],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
            pids[kind]=proc.pid
    (OUT/'current-run.txt').write_text(name)
    (OUT/'getup-success-launch.json').write_text(json.dumps(dict(run=name,observers=pids,prepared=plan),indent=2))
    print(json.dumps(dict(run=name,observers=pids)),flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
