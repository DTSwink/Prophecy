"""Resume the locomotion branch unchanged after a provider billing shutdown."""
import hashlib,json,subprocess,sys,time,zipfile
from pathlib import Path
import deploy_locomotion_branch as d

def prepare():
    active=json.loads((d.OUT/'active_run.json').read_text())
    plan=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    c=d.cloud.s3();prefix='mimickit/pipeline_20261014/runs/'+active['run']+'/'
    cp=json.loads(c.get_object(Bucket=d.cloud.rp.VOLUME_ID,Key=prefix+'latest_verified.json')['Body'].read())
    dest=d.OUT/'preserved-latest'/active['run']/Path(cp['key']).name;dest.parent.mkdir(parents=True,exist_ok=True)
    c.download_file(d.cloud.rp.VOLUME_ID,cp['key'],str(dest))
    assert hashlib.sha256(dest.read_bytes()).hexdigest()==cp['sha256']
    with zipfile.ZipFile(dest) as z:assert z.testzip() is None
    cp.update(local=str(dest),preserved_key=cp['key'])
    assert hashlib.sha256(Path(plan['source']['local']).read_bytes()).hexdigest()==plan['source']['sha256']
    d.save('funds-resume-before-plan',plan);d.save('funds-resume-old-launch',json.loads((d.OUT/'launch.json').read_text()))
    d.save('funds-resume-checkpoint',cp)
    print(json.dumps(cp),flush=True)

def start():
    pod=d.cloud.state()['pod_id'];assert pod=='q764mqd40pabiq'
    p=d.cloud.rp.request_json('GET','/pods/'+pod)
    assert p['desiredStatus']=='EXITED' and 0<float(p['costPerHr'])<=.59
    marker=d.OUT/'funds-resume-verified';marker.unlink(missing_ok=True)
    guard=f'''import sys,time
from pathlib import Path
sys.path.insert(0,{str(d.ROOT/'Labs/MimicKitTraining')!r})
import deploy_locomotion_branch as d
from billing_stop import stop_and_confirm
end=time.time()+600
while time.time()<end and not Path({str(marker)!r}).exists():time.sleep(2)
if not Path({str(marker)!r}).exists():stop_and_confirm({pod!r},d.cloud.rp.load_api_key(),Path({str(d.OUT/'funds-resume-timeout.json')!r}),'Resume not verified within ten minutes')
'''
    with (d.OUT/'funds-resume-guard.log').open('ab') as log:
        g=subprocess.Popen([sys.executable,'-c',guard],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
    d.save('funds-resume-guard',dict(pid=g.pid,pod=pod,deadline=time.time()+600))
    try:d.cloud.rp.request_json('POST','/pods/'+pod+'/start')
    except Exception:
        marker.touch()
        raise
    print('Pod start accepted; setup guard active',flush=True)
    d.cloud.connect()
    print(d.remote('''from pathlib import Path
import json
r=Path('/workspace/mimickit_trial');p=r/'runs'/'20261021_231729_uefn_locomotion_pelvis_velocity5_1024'
out={'venv':(r/'venv/bin/python').exists(),'private':(r/'private.json').exists(),'archives':[f.name for f in p.glob('checkpoint*.zip')]}
for name in ['checkpoint_status.json','backup_status.json','status.json']:
 if (p/name).exists():
  v=json.loads((p/name).read_text());out[name]=v if name!='status.json' else {k:v.get(k) for k in ['state','samples','iteration']}
print(json.dumps(out))
'''),flush=True)

def replace():
    old=d.cloud.state();assert old['pod_id']=='q764mqd40pabiq'
    assert d.cloud.rp.request_json('GET','/pods/'+old['pod_id'])['desiredStatus']=='EXITED'
    dest=d.OUT/'retained-pods'/old['pod_id'];dest.mkdir(parents=True,exist_ok=True)
    moved=[]
    for name in ['pod.json','runtime_control.json','active_run.json']:
        src=d.OUT/name;target=dest/(str(int(time.time()))+'-'+name)
        assert src.resolve().is_relative_to(d.OUT.resolve()) and target.resolve().is_relative_to(d.OUT.resolve())
        src.replace(target);moved.append((src,target))
    plan=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    plan['checkpoint']=json.loads((d.OUT/'funds-resume-checkpoint.json').read_text());d.save('getup-success-prepared',plan)
    try:d.allocate()
    except Exception:
        if not (d.OUT/'pod.json').exists():
            for src,target in moved:target.replace(src)
        raise
    d.provision()

def launch():
    plan=json.loads((d.OUT/'getup-success-prepared.json').read_text());cp=json.loads((d.OUT/'funds-resume-checkpoint.json').read_text());source=plan['source']
    code='''import json,hashlib,zipfile,io
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial');p=json.loads((r/'private.json').read_text());c=boto3.client('s3',**p['s3'])
for key,sha,filename in ARTIFACTS:
 data=c.get_object(Bucket='aj7d2jzwuq',Key=key)['Body'].read();assert hashlib.sha256(data).hexdigest()==sha
 (r/filename).write_bytes(data)
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
p['resume_checkpoint']=CHECKPOINT
(r/'private.json').write_text(json.dumps(p));(r/'stop.request').unlink(missing_ok=True)
print('Latest checkpoint and unchanged source verified')
'''.replace('ARTIFACTS',repr([(cp['key'],cp['sha256'],'resume.zip'),(source['key'],source['sha256'],'source.zip')])).replace('CHECKPOINT',repr(dict(key=cp['key'],sha256=cp['sha256'])))
    print(d.remote(code,timeout=60),flush=True)
    plan.update(checkpoint=cp,worlds=1024,run_suffix='uefn_locomotion_pelvis_velocity5_1024')
    d.save('getup-success-prepared',plan);d.launch()

if __name__=='__main__':globals()[sys.argv[1]]()
