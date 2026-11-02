"""Restore the preserved pre-experiment source and checkpoint on the same pod."""
import hashlib, json, sys, zipfile, io
from pathlib import Path
import yaml
import deploy_locomotion_branch as d
import restart_locomotion_ae as r

OUT = d.OUT / 'idle-rollback-20261029'
OUT.mkdir(exist_ok=True)
OLD_RUN = '20261028_225111_uefn_locomotion_idle_recovery_2048'

def save(name, value):
    (OUT / (name + '.json')).write_text(json.dumps(value, indent=2))

def prepare():
    previous = json.loads((d.OUT/'idle-recovery-20261028/previous-plan.json').read_text())
    rejected = json.loads((d.OUT/'idle-recovery-20261028/prepared.json').read_text())
    plan = dict(previous, checkpoint=rejected['checkpoint'], run_suffix='uefn_locomotion_leg7_idle3_restored_2048')
    cp, src = plan['checkpoint'], plan['source']
    for item in (cp, src):
        assert hashlib.sha256(Path(item['local']).read_bytes()).hexdigest() == item['sha256']
        with zipfile.ZipFile(item['local']) as z: assert z.testzip() is None
    with zipfile.ZipFile(cp['local']) as z, zipfile.ZipFile(src['local']) as source:
        for name in ['engine_config.yaml','env_config.yaml','agent_config.yaml']:
            a = yaml.safe_load(z.read(name)); b = yaml.safe_load(source.read('prepared/'+name))
            if name == 'agent_config.yaml': b['actor_optimizer']['learning_rate'] = 1.125e-6
            assert a == b, name
        import torch
        state = torch.load(io.BytesIO(z.read('resume_state.pt')), map_location='cpu', weights_only=False)
        save('checkpoint-state', {k: state[k] for k in ['completed_iteration','samples']})
    save('prepared', plan)
    save('rejected-plan', json.loads((d.OUT/'getup-success-prepared.json').read_text()))
    save('rejected-active', json.loads((d.OUT/'active_run.json').read_text()))
    # Reconstruct the old immutable ZIP from shared entries and an exact metadata delta.
    import pickle
    overlay = OUT/'restore-overlay.zip'
    with zipfile.ZipFile(src['local']) as old, zipfile.ZipFile(rejected['source']['local']) as new, zipfile.ZipFile(overlay,'w',zipfile.ZIP_DEFLATED) as delta:
        delta.writestr('infos.pkl', pickle.dumps(old.infolist()))
        for info in old.infolist():
            data = old.read(info.filename)
            if info.filename not in new.namelist() or data != new.read(info.filename): delta.writestr(info.filename, data)
    d.cloud.rp.scp(d.cloud.state()['connection'], overlay, '/workspace/mimickit_trial/restore-overlay.zip', timeout=40)
    code = '''from pathlib import Path
import zipfile,pickle,hashlib,json
r=Path('/workspace/mimickit_trial')
assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==REJECTED
with zipfile.ZipFile(r/'source.zip') as current,zipfile.ZipFile(r/'restore-overlay.zip') as delta,zipfile.ZipFile(r/'restore-source.zip','w') as dst:
 for info in pickle.loads(delta.read('infos.pkl')):
  dst.writestr(info,delta.read(info.filename) if info.filename in delta.namelist() else current.read(info.filename))
assert hashlib.sha256((r/'restore-source.zip').read_bytes()).hexdigest()==SOURCE
cp=r/'runs'/CPRUN/CPNAME
assert hashlib.sha256(cp.read_bytes()).hexdigest()==CPSHA
assert (r/'runtime-freeze.txt').exists()
print(json.dumps(dict(source_verified=True,checkpoint_verified=True)))
'''.replace('REJECTED',repr(rejected['source']['sha256'])).replace('SOURCE',repr(src['sha256'])).replace('CPRUN',repr(cp['key'].split('/')[-2])).replace('CPNAME',repr(Path(cp['key']).name)).replace('CPSHA',repr(cp['sha256']))
    result=json.loads(r.remote(code, timeout=35));save('staged',result);print(json.dumps(result),flush=True)

def stop():
    assert json.loads((OUT/'staged.json').read_text())['checkpoint_verified']
    active=json.loads((d.OUT/'active_run.json').read_text());assert active['run']==OLD_RUN
    plan=json.loads((OUT/'prepared.json').read_text())
    d.save('ae30-switch',dict(old_run=OLD_RUN,pod=active['pod'],source=plan['source']))
    r.stop()

def launch():
    plan=json.loads((OUT/'prepared.json').read_text());cp=plan['checkpoint'];src=plan['source']
    code='''from pathlib import Path
import hashlib,json,shutil,zipfile
r=Path('/workspace/mimickit_trial');p=r/'runs'/OLD
assert (p/'finished.json').exists(),'Trainer still finishing'
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:args=(proc/'cmdline').read_bytes().split(b'\\0')
 except OSError:continue
 assert b'/workspace/mimickit_trial/pipeline/train.py' not in args,'Trainer still alive'
backup=json.loads((p/'backup_status.json').read_text())
assert backup['key'].endswith('_final.zip')
assert hashlib.sha256((r/'restore-source.zip').read_bytes()).hexdigest()==SOURCE
original=r/'runs'/CPRUN/CPNAME
assert hashlib.sha256(original.read_bytes()).hexdigest()==CPSHA
shutil.copyfile(original,r/'resume.zip');shutil.copyfile(r/'restore-source.zip',r/'source.zip')
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
inactive=r/'pipeline/idle_recovery_reward.py'
if inactive.exists():inactive.rename(r/'rejected-idle-recovery-reward.py')
c=json.loads((r/'private.json').read_text());c['resume_checkpoint']=CP;(r/'private.json').write_text(json.dumps(c))
(r/'stop.request').unlink(missing_ok=True)
print(json.dumps(dict(rejected_final=backup,rejected_finished=json.loads((p/'finished.json').read_text()),restored_sha=CPSHA,source_sha=SOURCE)))
'''.replace('OLD',repr(OLD_RUN)).replace('SOURCE',repr(src['sha256'])).replace('CPRUN',repr(cp['key'].split('/')[-2])).replace('CPNAME',repr(Path(cp['key']).name)).replace('CPSHA',repr(cp['sha256'])).replace('CP',repr(dict(key=cp['key'],sha256=cp['sha256'])))
    result=json.loads(r.remote(code,timeout=35));save('promotion',result)
    d.save('getup-success-prepared',plan)
    # Superseded comparison artifacts remain evidence, never an automatic next action.
    compare=d.OUT/'idle-comparison-20261028/plan.json'
    p=json.loads(compare.read_text());p['state']='cancelled_by_user_rollback';p['execution_authorized']=False
    compare.write_text(json.dumps(p,indent=2))
    d.launch()

def verify():
    plan=json.loads((OUT/'prepared.json').read_text());active=json.loads((d.OUT/'active_run.json').read_text())
    assert active['run'].endswith(plan['run_suffix'])
    code='''from pathlib import Path
import json,time,hashlib,zipfile,yaml,numpy as np
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
assert not any((p/n).exists() for n in ['failure.json','numerical_failure.json','backup_errors.json','finished.json'])
if not all((p/n).exists() for n in ['status.json','backup_status.json','replay.npz']):
 print(json.dumps(dict(ready=False,log=(r/(NAME+'.log')).read_text()[-700:])));raise SystemExit
s=json.loads((p/'status.json').read_text());status={k:s.get(k) for k in ['state','iteration','samples','worlds','updated_unix','training_transitions_per_second']}
if s['iteration']<274964:
 print(json.dumps(dict(ready=False,status=status)));raise SystemExit
assert s['state']=='training' and time.time()-s['updated_unix']<120 and s['worlds']==2048
assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==SOURCE
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==CHECKPOINT
with zipfile.ZipFile(r/'resume.zip') as z:
 for name in ['engine_config.yaml','env_config.yaml','agent_config.yaml']:
  assert yaml.safe_load(z.read(name))==yaml.safe_load((p/name).read_text()),name
dispatch=json.loads((p/'lossless_dispatch.json').read_text());assert dispatch['worlds']==2048 and dispatch['reference_done_graphs']
z=np.load(p/'replay.npz');rows=json.loads(str(z['metadata']))['replay_rows'];forms=[]
for i,row in enumerate(rows):
 names=row['loss_term_names'];assert 'leg_reversal' in names and 'foot_linear_reversal' in names and 'foot_angular_reversal' in names
 assert not any(n in names for n in ['idle_stop','idle_pose','idle_smooth','idle_steps','idle_slip','idle_posture'])
 assert row['reward_from_loss'] in ['reciprocal_sum','reciprocal_sum_plus_getup_head_height'],row['reward_from_loss']
 assert row['frame_com2_reward_multiplier'];forms.append(row['reward_from_loss'])
 assert np.isfinite(z['loss_terms'+('' if i==0 else '_'+str(i))]).all()
b=json.loads((p/'backup_status.json').read_text())
import boto3
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);body=c.get_object(Bucket='aj7d2jzwuq',Key=b['key'])['Body'];h=hashlib.sha256()
for block in iter(lambda:body.read(1024*1024),b''):h.update(block)
body.close();assert h.hexdigest()==b['sha256']
resume=json.loads((p/'resume.json').read_text())
print(json.dumps(dict(ready=True,run=NAME,status=status,backup=b,replay_rows=len(rows),reward_forms=sorted(set(forms)),resume=resume,source_sha256=SOURCE,config_match=True)))
'''.replace('NAME',repr(active['run'])).replace('SOURCE',repr(plan['source']['sha256'])).replace('CHECKPOINT',repr(plan['checkpoint']['sha256']))
    result=json.loads(r.remote(code,timeout=45));save('live-verification',result)
    if result['ready']:
        print(r.remote("from pathlib import Path;Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch();print('Verified handoff complete')",timeout=20),flush=True)
    print(json.dumps({k:v for k,v in result.items() if k!='resume'}),flush=True)

if __name__=='__main__': globals()[sys.argv[1]]()
