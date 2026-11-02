"""Explicit recovery-only native-to-custom final pass; preserve every learned checkpoint."""
import hashlib,json,subprocess,sys,time,zipfile
from pathlib import Path
import yaml
import resume_getup_success as r
from backup import verified_readback
OUT=r.OUT/'custom-solver-final-pass'
OUT.mkdir(exist_ok=True)
BASE='/workspace/mimickit_trial'

def remote(code,timeout=60):
    p=subprocess.run(r.cloud.rp.ssh_base(r.cloud.state()['connection'])+[BASE+'/venv/bin/python','-'],input=code,
        capture_output=True,text=True,timeout=timeout)
    if p.returncode:raise RuntimeError(p.stdout[-3000:]+p.stderr[-3000:])
    return p.stdout

def prepare():
    plan=json.loads((r.OUT/'getup-success-prepared.json').read_text())
    active=json.loads((r.OUT/'active_run.json').read_text())
    assert active['pod']==r.cloud.state()['pod_id']=='0to3wg3r3n926h'
    (OUT/'previous-plan.json').write_text(json.dumps(plan,indent=2))
    (OUT/'previous-active.json').write_text(json.dumps(active,indent=2))
    with zipfile.ZipFile(plan['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    cfg=yaml.safe_load(entries['prepared/engine_config.yaml'])
    cfg.pop('uefn_native_profile')
    cfg.update(uefn_bounded_velocity_motors=True,uefn_jolt_contact_profile=True,transfer_floor_aware_projection=True)
    with zipfile.ZipFile(r.OUT/'reciprocal-source.zip') as z:
        assert cfg==yaml.safe_load(z.read('prepared/engine_config.yaml'))
        for n in entries:
            if n.startswith('assets/MimicKitTransfer/'):
                assert entries[n]==z.read(n),'Custom solver differs from the previously used version: '+n
    entries['prepared/engine_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    # Apply only the explicit resume switch to the running source; other chats' edits stay out.
    train=entries['pipeline/train.py'].decode().replace('\r\n','\n')
    anchor="    parser.add_argument('--resume-position-leeway',action='store_true',"
    assert train.count(anchor)==1
    train=train.replace(anchor,"    parser.add_argument('--resume-custom-physics',action='store_true')\n"+anchor)
    anchor="                        else:\n                            assert new['uefn_bounded_velocity_motors'] is True"
    assert train.count(anchor)==1
    train=train.replace(anchor,"                        else:\n                            if a.resume_custom_physics:\n                                assert old.get('uefn_native_profile') in (None,'native_runlr_soft_contact_20261018')\n                                old.pop('uefn_native_profile',None)\n                                assert new.get('transfer_floor_aware_projection') is True\n                            assert new['uefn_bounded_velocity_motors'] is True")
    anchor="    if a.valid_reset_pose_pool:\n        atomic_json(directory/'reset_pose_pool.json',env.reset_pose_pool_report)"
    assert train.count(anchor)==1
    train=train.replace(anchor,"    if a.resume_custom_physics:\n        assert type(env._engine).__name__=='ContactTransferEngine'\n        assert env._engine.transfer_floor_guard is not None\n        atomic_json(directory/'custom_physics.json',dict(engine=type(env._engine).__name__,floor_guard=True,physics_hz=engine_config['sim_freq'],policy_hz=engine_config['control_freq']))\n"+anchor)
    compile(train,'train.py','exec')
    entries['pipeline/train.py']=train.encode()
    p=OUT/'source.zip'
    with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    with zipfile.ZipFile(plan['source']['local']) as old:
        changed=[n for n in entries if entries[n]!=old.read(n)]
    assert sorted(changed)==['pipeline/train.py','prepared/engine_config.yaml']
    sha=hashlib.sha256(p.read_bytes()).hexdigest();key='mimickit/pipeline_20261014/equipment/custom-final/source_'+sha[:12]+'.zip'
    c=r.cloud.s3();c.upload_file(str(p),r.cloud.rp.VOLUME_ID,key);verified_readback(c,r.cloud.rp.VOLUME_ID,key,sha)
    source=dict(local=str(p),key=key,sha256=sha)
    (OUT/'source.json').write_text(json.dumps(source,indent=2))
    # Stage without replacing files used by the running trainer.
    stage()

def stage():
    source=json.loads((OUT/'source.json').read_text())
    code="""import boto3,json,hashlib
from pathlib import Path
r=Path('/workspace/mimickit_trial');c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
p=r/'custom-final-source.zip';c.download_file('aj7d2jzwuq',KEY,str(p));assert hashlib.sha256(p.read_bytes()).hexdigest()==SHA
print('Source staged; only engine configuration and explicit resume check changed')
""".replace('KEY',repr(source['key'])).replace('SHA',repr(source['sha256']))
    print(remote(code,90),flush=True)

def stop():
    active=json.loads((OUT/'previous-active.json').read_text())
    assert json.loads((r.OUT/'active_run.json').read_text())==active
    snapshot=json.loads((OUT/'MimicKitEquipment-snapshot.json').read_text())['preserved']
    assert hashlib.sha256(Path(snapshot['local']).read_bytes()).hexdigest()==snapshot['sha256']
    code='''import os,signal,json,subprocess,time
from pathlib import Path
r=Path('/workspace/mimickit_trial');name=NAME
a=json.loads((r/(name+'-launch.json')).read_text())
assert name.encode() in (Path('/proc')/str(a['pid'])/'cmdline').read_bytes()
assert b'failure_stop.py' in (Path('/proc')/str(a['exit_guard_pid'])/'cmdline').read_bytes()
watch="import sys,time,json;from pathlib import Path;sys.path.insert(0,'/workspace/mimickit_trial/pipeline');from billing_stop import stop_and_confirm;r=Path('/workspace/mimickit_trial');end=time.time()+900;c=json.loads((r/'private.json').read_text())\\nwhile time.time()<end and not (r/'custom_final_verified').exists():time.sleep(2)\\nif not (r/'custom_final_verified').exists():stop_and_confirm(c['pod_id'],c['runpod_api_key'],r/'custom_final_timeout.json','Custom solver handoff exceeded fifteen minutes')"
(r/'custom_final_verified').unlink(missing_ok=True)
with (r/'custom-final-watch.log').open('ab') as log:
 p=subprocess.Popen([str(r/'venv/bin/python'),'-c',watch],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
os.kill(a['exit_guard_pid'],signal.SIGTERM)
(r/'runs'/name/'stop.request').touch()
print(json.dumps(dict(run=name,watchdog=p.pid,started_unix=time.time())))
'''.replace('NAME',repr(active['run']))
    result=json.loads(remote(code));(OUT/'stop.json').write_text(json.dumps(result));print(result,flush=True)

def preserve():
    old=json.loads((OUT/'previous-active.json').read_text())['run']
    code='''import json,time,hashlib,shutil
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
for _ in range(25):
 if (p/'finished.json').exists():break
 assert not (p/'failure.json').exists(),'Training failed during final save'
 time.sleep(2)
assert (p/'finished.json').exists(),'Final save pending'
b=json.loads((p/'backup_status.json').read_text());assert b['key'].endswith('_final.zip')
f=p/Path(b['key']).name;assert hashlib.sha256(f.read_bytes()).hexdigest()==b['sha256']
shutil.copyfile(f,r/'resume.zip');print(json.dumps(b))
'''.replace('NAME',repr(old))
    cp=json.loads(remote(code,60));p=r.OUT/'preserved-latest'/old/Path(cp['key']).name;p.parent.mkdir(parents=True,exist_ok=True)
    part=p.with_suffix('.part');r.cloud.s3().download_file(r.cloud.rp.VOLUME_ID,cp['key'],str(part))
    assert part.stat().st_size==cp['bytes'] and hashlib.sha256(part.read_bytes()).hexdigest()==cp['sha256']
    with zipfile.ZipFile(part) as z:assert z.testzip() is None
    part.replace(p);cp.update(local=str(p),preserved_key=cp['key'],verified_local_unix=time.time())
    (OUT/'preserved.json').write_text(json.dumps(cp,indent=2))
    (r.OUT/'latest-local-checkpoint.json').write_text(json.dumps(cp,indent=2))
    plan=json.loads((OUT/'previous-plan.json').read_text())
    plan.update(checkpoint=cp,source=json.loads((OUT/'source.json').read_text()),run_suffix='uefn_getup_custom_final_1024')
    plan.setdefault('training_overrides',{})['custom_physics']=True
    (r.OUT/'getup-success-prepared.json').write_text(json.dumps(plan,indent=2))
    print(json.dumps(cp),flush=True)

def launch():
    source=json.loads((OUT/'source.json').read_text())
    print(remote("from pathlib import Path;import hashlib;r=Path('/workspace/mimickit_trial');p=r/'custom-final-source.zip';assert hashlib.sha256(p.read_bytes()).hexdigest()=="+repr(source['sha256'])+";p.replace(r/'source.zip');print('Verified source installed')"),flush=True)
    r.launch()

def status():
    name=json.loads((r.OUT/'active_run.json').read_text())['run']
    print(remote("from pathlib import Path;import json;r=Path('/workspace/mimickit_trial');p=r/'runs'/"+repr(name)+";d={n:json.loads((p/n).read_text()) for n in ['status.json','backup_status.json','custom_physics.json','failure.json','backup_errors.json'] if (p/n).exists()};s=d.get('status.json',{});d['status.json']={k:s[k] for k in ['state','iteration','samples','updated_unix','iteration_seconds','training_transitions_per_second'] if k in s};d['log_tail']=(r/"+repr(name+'.log')+").read_text(errors='replace')[-2200:];print(json.dumps(d))"),flush=True)

def verify():
    name=json.loads((r.OUT/'active_run.json').read_text())['run']
    cp=json.loads((OUT/'preserved.json').read_text())
    code='''import json,hashlib,zipfile,re
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
s=json.loads((p/'status.json').read_text());b=json.loads((p/'backup_status.json').read_text());physics=json.loads((p/'custom_physics.json').read_text())
logged=[int(x) for x in re.findall(r'\|\s+Iteration\s+\|\s+(\d+)',(r/(NAME+'.log')).read_text(errors='replace'))]
assert s['state']=='training' and logged and max(logged)>=3
assert physics==dict(engine='ContactTransferEngine',floor_guard=True,physics_hz=240,policy_hz=30)
assert not (p/'failure.json').exists() and not (p/'backup_errors.json').exists()
assert b['key'].split('/')[-2]==NAME
assert hashlib.sha256((p/Path(b['key']).name).read_bytes()).hexdigest()==b['sha256']
assert (p/'replay.npz').exists()
print(json.dumps(dict(status=s,backup=b,physics=physics,completed_iteration=RESUME_STEP+1+max(logged),resume=json.loads((p/'resume.json').read_text()))))
'''.replace('NAME',repr(name)).replace('RESUME_STEP',str(int(re.search(r'checkpoint_(\d+)',cp['key'])[1])))
    result=json.loads(remote(code));verified_readback(r.cloud.s3(),r.cloud.rp.VOLUME_ID,result['backup']['key'],result['backup']['sha256'])
    remote("from pathlib import Path;Path('/workspace/mimickit_trial/custom_final_verified').touch()")
    (OUT/'verified.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(iteration=result['completed_iteration'],samples=result['status']['samples'],speed=result['status'].get('training_transitions_per_second'),physics=result['physics'],backup=result['backup'])),flush=True)

if __name__=='__main__':
    import re
    globals()[sys.argv[1]]()
