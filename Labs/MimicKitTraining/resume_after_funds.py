"""Resume either current physical training branch without changing its settings."""
import hashlib,json,os,shlex,subprocess,sys,time,zipfile
from pathlib import Path
from datetime import datetime

ROOT=Path(__file__).resolve().parents[2]
BRANCH=sys.argv[1]
assert BRANCH in ('MimicKitEquipment','MimicKitLocomotion')
OUT=ROOT/'Saved'/BRANCH
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
from billing_stop import stop_and_confirm

def save(name,data):
    (OUT/('funds-resume-'+name+'.json')).write_text(json.dumps(data,indent=2))
def remote(code,timeout=45,venv=False):
    return cloud.ssh(('/workspace/mimickit_trial/venv/bin/python' if venv else 'python')+' -c '+shlex.quote(code),timeout=timeout)

def preserve():
    import boto3
    from botocore.config import Config
    a=json.loads((OUT/'active_run.json').read_text());plan=json.loads((OUT/'getup-success-prepared.json').read_text())
    c=boto3.client('s3',**cloud.credentials(),config=Config(connect_timeout=10,read_timeout=30,retries={'total_max_attempts':3}))
    prefix='mimickit/pipeline_20261014/runs/'+a['run']+'/'
    cp=json.loads(c.get_object(Bucket=cloud.rp.VOLUME_ID,Key=prefix+'latest_verified.json')['Body'].read())
    assert cp['key'].startswith(prefix)
    path=OUT/'preserved-latest'/a['run']/Path(cp['key']).name;path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.part')
    c.download_file(cloud.rp.VOLUME_ID,cp['key'],str(tmp))
    assert hashlib.sha256(tmp.read_bytes()).hexdigest()==cp['sha256']
    with zipfile.ZipFile(tmp) as z:assert z.testzip() is None
    tmp.replace(path);cp.update(local=str(path),preserved_key=cp['key'],verified_local_unix=time.time())
    assert hashlib.sha256(Path(plan['source']['local']).read_bytes()).hexdigest()==plan['source']['sha256']
    save('prepared',dict(old_active=a,old_plan=plan,checkpoint=cp,source=plan['source']))
    print(json.dumps(dict(branch=BRANCH,checkpoint=cp)),flush=True)

def guard():
    state=json.loads((OUT/'funds-resume-start.json').read_text());marker=OUT/'funds-resume-verified'
    while time.time()<state['deadline'] and not marker.exists():time.sleep(2)
    if not marker.exists():stop_and_confirm(state['pod'],cloud.rp.load_api_key(),OUT/'funds-resume-guard-stop.json','Funds resume setup exceeded ten minutes')

def start():
    p=cloud.state();current=cloud.rp.request_json('GET','/pods/'+p['pod_id'])
    assert current['desiredStatus']=='EXITED';assert float(current['costPerHr'])<=.59
    (OUT/'funds-resume-verified').unlink(missing_ok=True)
    save('start',dict(pod=p['pod_id'],deadline=time.time()+600))
    with (OUT/'funds-resume-guard.log').open('ab') as log:
        g=subprocess.Popen([sys.executable,__file__,BRANCH,'guard'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
    try:
        cloud.rp.request_json('POST','/pods/'+p['pod_id']+'/start')
    except Exception:
        current=cloud.rp.request_json('GET','/pods/'+p['pod_id'])
        if current['desiredStatus']=='EXITED':
            (OUT/'funds-resume-verified').touch()
        raise
    print(json.dumps(dict(branch=BRANCH,started=p['pod_id'],guard=g.pid)),flush=True)
    cloud.connect()
    code="from pathlib import Path;import json;r=Path('/workspace/mimickit_trial');v=r/'venv';print(json.dumps(dict(venv=(v/'bin/python').exists(),source=(r/'source.zip').exists(),private=(r/'private.json').exists())))"
    print(remote(code),flush=True)

def runtime():
    ready=json.loads(remote("from pathlib import Path;import json;r=Path('/workspace/mimickit_trial');v=r/'venv';print(json.dumps(dict(ready=(v/'bin/python').exists())))"))
    if ready['ready']:print('Runtime retained',flush=True);return
    remote("from pathlib import Path;p=Path('/workspace/mimickit_trial/venv');p.unlink() if p.is_symlink() and not p.exists() else None")
    cloud.prepare_runtime_cache()
    print(remote("import subprocess;from pathlib import Path;r=Path('/workspace/mimickit_trial');log=(r/'funds-runtime.log').open('ab');p=subprocess.Popen(['timeout','240','python','pipeline/runtime_cache.py','restore'],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True);print(p.pid)"),flush=True)

def launch():
    plan=json.loads((OUT/'funds-resume-prepared.json').read_text());cp=plan['checkpoint'];source=plan['source'];a=plan['old_active']
    code='''import json,hashlib,zipfile,shutil,boto3,re
from pathlib import Path
r=Path('/workspace/mimickit_trial');cfg=json.loads((r/'private.json').read_text());c=boto3.client('s3',**cfg['s3'])
old=r/'runs'/OLD
selected=int(re.search(r'checkpoint_(\d+)',CPKEY)[1])
newer=[p.name for p in old.glob('checkpoint_*.zip') if int(re.search(r'checkpoint_(\d+)',p.name)[1])>selected]
assert not newer,'Newer retained checkpoints require preservation: '+str(newer)
for key,sha,name in [(CPKEY,CPSHA,'resume.zip'),(SRCKEY,SRCSHA,'source.zip')]:
 p=r/name
 if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:
  tmp=p.with_suffix('.download');c.download_file('aj7d2jzwuq',key,str(tmp));assert hashlib.sha256(tmp.read_bytes()).hexdigest()==sha;tmp.replace(p)
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
cfg['resume_checkpoint']=dict(key=CPKEY,sha256=CPSHA);(r/'private.json').write_text(json.dumps(cfg));(r/'stop.request').unlink(missing_ok=True)
print('Latest checkpoint and exact source verified')
'''.replace('OLD',repr(a['run'])).replace('CPKEY',repr(cp['key'])).replace('CPSHA',repr(cp['sha256'])).replace('SRCKEY',repr(source['key'])).replace('SRCSHA',repr(source['sha256']))
    print(remote(code,90,True),flush=True)
    now=datetime.now().astimezone();suffix=plan['old_plan']['run_suffix'];name=now.strftime('%Y%m%d_%H%M%S')+'_'+suffix
    args=list(a['command'][3:]);assert args[0]=='--name';args[1]=name
    subprocess.run([sys.executable,str(Path(__file__).with_name('start_training.py')),'--keep-deadline','--seconds','86400','--source-package',source['local'],'--source-sha256',source['sha256'],'--',*args],check=True)
    manifest=json.loads((OUT/(a['run']+'-dashboard.json')).read_text())
    manifest['runtime_control']['pod_id']=cloud.state()['pod_id']
    manifest['runs']=[dict(name=now.strftime('%Y-%m-%d_%H-%M-%S')+'_'+suffix,objective='uefn_omni_absolute_walk',training_outcomes=True,sources=[str(Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name))])]
    path=OUT/(name+'-dashboard.json');path.write_text(json.dumps(manifest,indent=2));observers={}
    for kind,argv in [('bridge',['--name',name]),('dashboard',[str(path)])]:
        with (OUT/(name+'-'+kind+'.log')).open('ab') as log:
            p=subprocess.Popen([sys.executable,str(Path(__file__).with_name(kind+'.py')),*argv],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
        observers[kind]=p.pid
    base=plan['old_plan'];base.update(checkpoint=cp);(OUT/'getup-success-prepared.json').write_text(json.dumps(base,indent=2));(OUT/'current-run.txt').write_text(name)
    save('launch',dict(run=name,observers=observers,checkpoint=cp,source=source));print(json.dumps(dict(run=name,observers=observers)),flush=True)

def status():
    a=json.loads((OUT/'active_run.json').read_text());name=a['run']
    code="from pathlib import Path;import json;r=Path('/workspace/mimickit_trial');p=r/'runs'/"+repr(name)+";s=json.loads((p/'status.json').read_text()) if (p/'status.json').exists() else {};print(json.dumps({k:s.get(k) for k in ['state','iteration','samples','training_transitions_per_second']}));print('backup',(p/'backup_status.json').exists(),'failure',(p/'failure.json').exists());print((r/"+repr(name+'.log')+").read_text()[-500:])"
    print(remote(code),flush=True)

def verify():
    name=json.loads((OUT/'active_run.json').read_text())['run']
    code='''from pathlib import Path
import json,hashlib,boto3,re
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME;s=json.loads((p/'status.json').read_text());b=json.loads((p/'backup_status.json').read_text());cp=p/Path(b['key']).name
assert s['state']=='training' and not (p/'failure.json').exists()
assert s['iteration']>int(re.search(r'checkpoint_(\d+)',b['key'])[1])
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);stream=c.get_object(Bucket='aj7d2jzwuq',Key=b['key'])['Body'];h=hashlib.sha256()
for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
stream.close();assert h.hexdigest()==b['sha256']
print(json.dumps(dict(run=NAME,iteration=s['iteration'],samples=s['samples'],transitions_per_second=s.get('training_transitions_per_second'),backup=b,resume=json.loads((p/'resume.json').read_text()))))
'''.replace('NAME',repr(name))
    report=json.loads(remote(code,90,True));save('verification',report);(OUT/'funds-resume-verified').touch();print(json.dumps({k:v for k,v in report.items() if k!='resume'}),flush=True)

if __name__=='__main__':globals()[sys.argv[2]]()
