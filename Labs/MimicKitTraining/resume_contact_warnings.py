"""Continue the verified bounded recovery run with permissive contact diagnostics."""
import hashlib,json,shlex,sys,time,zipfile
from pathlib import Path
import resume_recovery_bounded as h
from backup import verified_readback

r=h.r
OUT=h.OUT/'unexpected-stop-20261023'
OLD_RUN='20261023_115010_uefn_getup_bounded_jolt40_1024'
OLD_SOURCE='1d8d01a041ae54a6ef91d023ff25254e7be786082da3b668569d992635776779'

def prepare():
    raise RuntimeError('Superseded: use the verified native161960 plan in native-restart-20261023; never rebuild from stale162261.')
    tests=json.loads((OUT/'warning-fix-tests.json').read_text())
    assert tests['captured_velocity_difference']==0 and tests['nonfinite_rejected']
    assert tests['all_points_retained'] and tests['distinct_normals_separated']
    plan=json.loads((r.OUT/'getup-success-prepared.json').read_text())
    assert plan['source']['sha256']==OLD_SOURCE
    source=Path(plan['source']['local']);assert hashlib.sha256(source.read_bytes()).hexdigest()==OLD_SOURCE
    (OUT/'previous-plan.json').write_text(json.dumps(plan,indent=2))
    c=r.cloud.s3();prefix='mimickit/pipeline_20261014/runs/'+OLD_RUN+'/'
    cp=json.loads(c.get_object(Bucket=r.cloud.rp.VOLUME_ID,Key=prefix+'latest_verified.json')['Body'].read())
    assert cp['key'].startswith(prefix) and cp['key'].endswith('checkpoint_0162261.zip')
    local=r.OUT/'preserved-latest'/OLD_RUN/Path(cp['key']).name;local.parent.mkdir(parents=True,exist_ok=True)
    part=local.with_suffix('.download');c.download_file(r.cloud.rp.VOLUME_ID,cp['key'],str(part))
    assert hashlib.sha256(part.read_bytes()).hexdigest()==cp['sha256']
    with zipfile.ZipFile(part) as z:assert z.testzip() is None
    part.replace(local);verified_readback(c,r.cloud.rp.VOLUME_ID,cp['key'],cp['sha256'])
    cp.update(local=str(local),preserved_key=cp['key'],verified_local_unix=time.time())
    (OUT/'preserved.json').write_text(json.dumps(cp,indent=2))
    with zipfile.ZipFile(source) as z:entries={n:z.read(n) for n in z.namelist()}
    changed=[]
    for name in ['contact_engine.py','contact_manifolds_gpu.py']:
        data=(r.ROOT/'Labs/MimicKitTransfer'/name).read_bytes();compile(data,name,'exec')
        entries['assets/MimicKitTransfer/'+name]=data;changed.append('assets/MimicKitTransfer/'+name)
    package=OUT/'source-contact-warnings.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries.items():z.writestr(name,data)
    sha=hashlib.sha256(package.read_bytes()).hexdigest();key='mimickit/pipeline_20261014/equipment/recovery-bounded/source_'+sha[:12]+'.zip'
    c.upload_file(str(package),r.cloud.rp.VOLUME_ID,key);verified_readback(c,r.cloud.rp.VOLUME_ID,key,sha)
    plan.update(checkpoint=cp,source=dict(local=str(package),key=key,sha256=sha),run_suffix='uefn_getup_bounded_jolt40_warnings_1024')
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2))
    (r.OUT/'getup-success-prepared.json').write_text(json.dumps(plan,indent=2))
    print(json.dumps(dict(checkpoint=162261,source_sha256=sha,changed_files=changed,persistent_verified=True)),flush=True)

def stage():
    plan=json.loads((OUT/'prepared.json').read_text())
    code='''import json,hashlib,zipfile,boto3
from pathlib import Path
r=Path('/workspace/mimickit_trial');c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
for key,sha,name in ITEMS:
 p=r/name
 if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:
  part=p.with_suffix('.download');c.download_file('aj7d2jzwuq',key,str(part));assert hashlib.sha256(part.read_bytes()).hexdigest()==sha
  with zipfile.ZipFile(part) as z:assert z.testzip() is None
  part.replace(p)
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
print('Latest verified continuation and two-file warning fix staged')
'''.replace('ITEMS',repr([(plan['checkpoint']['key'],plan['checkpoint']['sha256'],'resume.zip'),(plan['source']['key'],plan['source']['sha256'],'source.zip')]))
    print(h.remote(code,120),flush=True)

def launch():r.launch()
def status():h.status()

def replace():
    # User authorized an equivalent GPU when L4 capacity is unavailable.
    gpu=sys.argv[2]
    assert gpu in ('NVIDIA GeForce RTX 4090','NVIDIA RTX 5000 Ada Generation','NVIDIA RTX 4000 Ada Generation','NVIDIA GeForce RTX 3090','NVIDIA RTX A5000','NVIDIA RTX A6000')
    h.replace(gpu=gpu)

def verify():
    name=json.loads((r.OUT/'active_run.json').read_text())['run'];assert 'bounded_jolt40_native161960' in name
    code='''from pathlib import Path
import json,hashlib
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
s=json.loads((p/'status.json').read_text());b=json.loads((p/'backup_status.json').read_text());ph=json.loads((p/'custom_physics.json').read_text())
assert s['state']=='training' and s['iteration']>=161972
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==EXPECTED
assert ph['solver']['profile']=='bounded_jolt_40_20' and ph['floor_guard'] and ph['physics_hz']==240 and ph['policy_hz']==30
assert not (p/'failure.json').exists() and not (p/'backup_errors.json').exists()
assert hashlib.sha256((p/Path(b['key']).name).read_bytes()).hexdigest()==b['sha256']
assert (p/'replay.npz').exists()
print(json.dumps(dict(run=NAME,status=s,backup=b,physics=ph,resume=json.loads((p/'resume.json').read_text()))))
'''.replace('NAME',repr(name)).replace('EXPECTED',repr(h.EXPECTED))
    report=json.loads(h.remote(code));verified_readback(r.cloud.s3(),r.cloud.rp.VOLUME_ID,report['backup']['key'],report['backup']['sha256'])
    (h.OUT/'native-restart-20261023/live-verified.json').write_text(json.dumps(report,indent=2));(r.OUT/'funds-resume-verified').touch()
    print(json.dumps(dict(run=name,iteration=report['status']['iteration'],speed=report['status']['training_transitions_per_second'],backup_verified=True)),flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
