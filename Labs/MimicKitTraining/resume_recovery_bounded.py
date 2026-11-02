"""Authorized recovery-only restart from native161960 after transfer validation.

Uses the existing recovery pod and established setup/failure billing guards.
No locomotion changes, checkpoint deletion, or implicit allocation.
"""
import hashlib,json,shlex,subprocess,sys,time,zipfile
from pathlib import Path
import resume_getup_success as r
from backup import verified_readback

OUT=r.ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023'
EXPECTED='0dc58150f87f1cb25816235f9e565638e9972d262b9203c5da0d14c0ea736a2b'
POD='0to3wg3r3n926h'

def remote(code,timeout=60):
    return r.cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=timeout)

def expected_pod():
    replacement=OUT/'replacement.json'
    return json.loads(replacement.read_text())['pod_id'] if replacement.exists() else POD

def replace(gpu='NVIDIA L4'):
    old=r.cloud.state();assert old['pod_id']==expected_pod()
    assert r.cloud.rp.request_json('GET','/pods/'+old['pod_id'])['desiredStatus']=='EXITED'
    # Retain every old identifier and the retained disk; only the local active pointer changes.
    (OUT/('retained-pod-'+old['pod_id']+'.json')).write_text(json.dumps(old,indent=2))
    (r.OUT/'pod.json').unlink()
    name='mimickit-recovery-bounded-'+str(int(time.time()))
    try:r.cloud.allocate(gpu,.59,cloud_type='SECURE' if '--secure' in sys.argv else 'COMMUNITY',seconds=600,name=name)
    except Exception:
        if not (r.OUT/'pod.json').exists():r.cloud.save(old)
        raise
    new=r.cloud.state();(OUT/'replacement.json').write_text(json.dumps(new,indent=2))
    control=json.loads((r.OUT/'runtime_control.json').read_text());control['pod_id']=new['pod_id'];control['updated_unix']=time.time()
    (r.OUT/'runtime_control.json').write_text(json.dumps(control))
    (r.OUT/'funds-resume-verified').unlink(missing_ok=True)
    (r.OUT/'funds-resume-start.json').write_text(json.dumps(dict(pod=new['pod_id'],deadline=time.time()+600)))
    with (r.OUT/'funds-resume-guard.log').open('ab') as log:
        proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name('resume_after_funds.py')),'MimicKitEquipment','guard'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
    print(json.dumps(dict(replacement=new['pod_id'],setup_guard=proc.pid,retained_old_disk=True)),flush=True)

def connect():
    assert r.cloud.state()['pod_id']==expected_pod()
    r.cloud.connect()
    print(r.cloud.ssh("mkdir -p /workspace/mimickit_trial && test -d /workspace/mimickit_trial"),flush=True)

def provision():
    assert r.cloud.state()['pod_id']==expected_pod()
    r.provision()

def runtime():r.runtime()

def setup_status():
    code="from pathlib import Path;import json;r=Path('/workspace/mimickit_trial');print(json.dumps(dict(download=(r/'success-download-ready').exists(),runtime=(r/'venv/bin/python').exists())));print((r/'success-runtime.log').read_text(errors='replace')[-900:] if (r/'success-runtime.log').exists() else (r/'success-download.log').read_text(errors='replace')[-900:])"
    print(r.remote(code),flush=True)

def pod_status():
    p=r.cloud.rp.request_json('GET','/pods/'+expected_pod())
    print(json.dumps({k:p.get(k) for k in ['id','desiredStatus','costPerHr','lastStatusChange','publicIp','portMappings']}),flush=True)

def prepare():
    assert r.cloud.state()['pod_id']==expected_pod()
    packet=json.loads((OUT/'prepared-bounded40.json').read_text())
    assert packet['profile']=='bounded_jolt_40_20'
    assert hashlib.sha256(Path(packet['source']).read_bytes()).hexdigest()==packet['sha256']
    test=json.loads((OUT/'custom-custom-packaged-bounded40-6.json').read_text())
    assert test['errors']==[0] and test['initial_velocity_error']<1e-3
    assert all(v['terminal']==2 for v in test['results'])
    runlr=json.loads((r.OUT/'optimization-followup/recovery-audit-register40r1.json').read_text())['runs'][0]
    assert runlr['first_done']==[300]*16 and runlr['first_flags']==[3]*16
    baseline=json.loads((OUT/'native-custom-batched-baseline-1024.json').read_text())
    faster=json.loads((OUT/'native-custom-batched-register40r1-1024.json').read_text())
    assert baseline['physics_ms_mean']/faster['physics_ms_mean']>2
    checked=json.loads((OUT/'matched-bounded-timing-40-1.0.json').read_text())
    assert checked['unsupported_error_preserved'] and checked['nonfinite_rejected']
    cp=json.loads((r.OUT/'custom-solver-final-pass/preserved.json').read_text())
    assert cp['sha256']==EXPECTED and 'checkpoint_0161960_final.zip' in cp['key']
    assert hashlib.sha256(Path(cp['local']).read_bytes()).hexdigest()==EXPECTED
    with zipfile.ZipFile(cp['local']) as z:assert z.testzip() is None
    c=r.cloud.s3();verified_readback(c,r.cloud.rp.VOLUME_ID,cp['key'],EXPECTED)
    key='mimickit/pipeline_20261014/equipment/recovery-bounded/source_'+packet['sha256'][:12]+'.zip'
    c.upload_file(packet['source'],r.cloud.rp.VOLUME_ID,key)
    verified_readback(c,r.cloud.rp.VOLUME_ID,key,packet['sha256'])
    plan=json.loads((r.OUT/'getup-success-prepared.json').read_text())
    if not (OUT/'before-restart-plan.json').exists():(OUT/'before-restart-plan.json').write_text(json.dumps(plan,indent=2))
    assert plan['worlds']==1024
    plan.update(checkpoint=cp,source=dict(local=packet['source'],key=key,sha256=packet['sha256']),run_suffix='uefn_getup_bounded_jolt40_1024')
    plan['training_overrides']['custom_physics']=True
    (OUT/'validated-restart-plan.json').write_text(json.dumps(plan,indent=2))
    (r.OUT/'getup-success-prepared.json').write_text(json.dumps(plan,indent=2))
    print(json.dumps(dict(checkpoint=161960,source_sha256=packet['sha256'],local_physics_speedup=baseline['physics_ms_mean']/faster['physics_ms_mean'],persistent_readback=True)),flush=True)

def stage():
    assert r.cloud.state()['pod_id']==expected_pod()
    plan=json.loads((OUT/'validated-restart-plan.json').read_text())
    code='''import json,hashlib,zipfile,boto3,shutil
from pathlib import Path
r=Path('/workspace/mimickit_trial')
assert shutil.disk_usage(r).free>2*1024**3,'Insufficient retained disk space'
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
for key,sha,name in ITEMS:
 p=r/name
 if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:
  part=p.with_suffix('.download');c.download_file('aj7d2jzwuq',key,str(part));assert hashlib.sha256(part.read_bytes()).hexdigest()==sha
  with zipfile.ZipFile(part) as z:assert z.testzip() is None
  part.replace(p)
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
print('Native161960 and bounded profile staged and verified')
'''.replace('ITEMS',repr([(plan['checkpoint']['key'],EXPECTED,'resume.zip'),(plan['source']['key'],plan['source']['sha256'],'source.zip')]))
    print(remote(code,120),flush=True)

def launch():
    r.launch()

def status():
    name=json.loads((r.OUT/'active_run.json').read_text())['run']
    assert 'bounded_jolt40' in name
    code='''from pathlib import Path
import json,re
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
s=json.loads((p/'status.json').read_text()) if (p/'status.json').exists() else {}
log=(r/(NAME+'.log')).read_text(errors='replace')
result={k:s.get(k) for k in ['state','iteration','samples','iteration_seconds','training_transitions_per_second']}
result.update(backup=(p/'backup_status.json').exists(),failure=(p/'failure.json').exists(),tail=log[-1300:])
print(json.dumps(result))
'''.replace('NAME',repr(name))
    print(remote(code),flush=True)

def verify():
    name=json.loads((r.OUT/'active_run.json').read_text())['run']
    assert 'bounded_jolt40' in name
    code='''from pathlib import Path
import json,hashlib,re
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
s=json.loads((p/'status.json').read_text());b=json.loads((p/'backup_status.json').read_text());ph=json.loads((p/'custom_physics.json').read_text())
assert s['state']=='training' and s['iteration']>=161965
assert ph['solver']['profile']=='bounded_jolt_40_20' and ph['floor_guard'] and ph['physics_hz']==240 and ph['policy_hz']==30
assert not (p/'failure.json').exists() and not (p/'backup_errors.json').exists()
assert hashlib.sha256((p/Path(b['key']).name).read_bytes()).hexdigest()==b['sha256']
assert (p/'replay.npz').exists()
resume=json.loads((p/'resume.json').read_text())
print(json.dumps(dict(run=NAME,status=s,backup=b,physics=ph,resume=resume)))
'''.replace('NAME',repr(name))
    report=json.loads(remote(code))
    verified_readback(r.cloud.s3(),r.cloud.rp.VOLUME_ID,report['backup']['key'],report['backup']['sha256'])
    (OUT/'live-verified.json').write_text(json.dumps(report,indent=2))
    (r.OUT/'funds-resume-verified').touch()
    print(json.dumps(dict(run=name,iteration=report['status']['iteration'],samples=report['status']['samples'],speed=report['status'].get('training_transitions_per_second'),backup_verified=True)),flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
