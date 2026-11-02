"""Guarded deployment of approved head reversal and COM2 reward multiplier."""
import json,sys,hashlib
from pathlib import Path
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
import resume_pushed_idle_penalty as handoff
OUT=d.OUT/'head-reversal-com2-20261025'

def upload():
    plan=json.loads((OUT/'prepared.json').read_text());previous=json.loads((OUT/'previous-plan.json').read_text())['previous_source']
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'overlay.zip','/workspace/mimickit_trial/head-com2-overlay.zip',timeout=40)
    code='''from pathlib import Path
import hashlib,json,zipfile,pickle,boto3
r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==OLD
out=r/'head-com2-check';out.mkdir(exist_ok=True)
with zipfile.ZipFile(r/'source.zip') as src,zipfile.ZipFile(r/'head-com2-overlay.zip') as delta,zipfile.ZipFile(r/'head-com2-source.zip','w') as dst:
 for info in pickle.loads(delta.read('infos.pkl')):dst.writestr(info,delta.read(info.filename) if info.filename in delta.namelist() else src.read(info.filename))
 for name in delta.namelist():
  if name!='infos.pkl':
   p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(delta.read(name))
data=(r/'head-com2-source.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);c.put_object(Bucket='aj7d2jzwuq',Key=KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()).hexdigest()==SHA
print('Candidate isolated; source upload and persistent readback verified')
'''.replace('OLD',repr(previous['sha256'])).replace('SHA',repr(plan['source']['sha256'])).replace('KEY',repr(plan['source']['key']))
    print(r.remote(code,timeout=60),flush=True)
    d.cloud.rp.scp(d.cloud.state()['connection'],Path(__file__).with_name('preflight_head_com2.py'),'/workspace/mimickit_trial/preflight_head_com2.py',timeout=30)
    print(r.remote("import subprocess;from pathlib import Path;r=Path('/workspace/mimickit_trial');log=(r/'head-com2-check/preflight.log').open('wb');p=subprocess.Popen(['timeout','150',str(r/'venv/bin/python'),'-u',str(r/'preflight_head_com2.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True);print(p.pid)",timeout=20),flush=True)

def status():
    print(r.remote("from pathlib import Path;import json;r=Path('/workspace/mimickit_trial/head-com2-check');print((r/'complete.json').read_text() if (r/'complete.json').exists() else (r/'failure.txt').read_text() if (r/'failure.txt').exists() else (r/'preflight.log').read_text()[-2000:])",timeout=20),flush=True)

def stop():
    result=json.loads(r.remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/head-com2-check/complete.json').read_text())",timeout=20));assert result['passed']
    (OUT/'preflight.json').write_text(json.dumps(result,indent=2))
    active=json.loads((d.OUT/'active_run.json').read_text());plan=json.loads((OUT/'prepared.json').read_text())
    assert active['pod']=='ghd13y3edq7ruw' and active['run']=='20261025_165654_uefn_locomotion_idle_prior_2048'
    d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod'],source=plan['source']))
    handoff.stop()

def verify():
    plan=json.loads((OUT/'prepared.json').read_text());active=json.loads((d.OUT/'active_run.json').read_text());name=active['run']
    assert name.endswith(plan['run_suffix'])
    code='''from pathlib import Path
import json,time,hashlib,numpy as np
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
s=json.loads((p/'status.json').read_text());b=json.loads((p/'backup_status.json').read_text())
assert s['state']=='training' and time.time()-s['updated_unix']<180
assert s['iteration']>=INITIAL+10
assert not (p/'finished.json').exists() and not (p/'backup_errors.json').exists()
assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==SHA
dispatch=json.loads((p/'lossless_dispatch.json').read_text())
assert dispatch['worlds']==2048 and dispatch['physics_kernel_intercepts']==dict(velocity=8,derivative=8)
assert dispatch['factor_intercepts']==16 and dispatch['cached_cholesky_intercepts']==16
assert dispatch['reference_done_graphs'] and dispatch['converged_newton_direction_skip']
z=np.load(p/'replay.npz');meta=json.loads(str(z['metadata']));rows=meta['replay_rows']
for row in rows:
 assert 'head_reversal' in row['loss_term_names'] and row['frame_com2_reward_multiplier']
 assert not row['com2_reward_gate']['require_both']
 assert min(row['frame_com2_reward_multiplier'])>=.00099
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
ev=EventAccumulator(str(p));ev.Reload();tags=ev.Tags()['scalars']
assert 'loss/head_reversal' in tags
print(json.dumps(dict(run=NAME,status={k:s.get(k) for k in ['state','iteration','samples','worlds','updated_unix','recent_iteration_mean_seconds','training_transitions_per_second','losses']},backup=b,dispatch=dispatch,replay_rows=len(rows),
 new_tags=[x for x in tags if 'head_reversal' in x or 'com2_multiplier' in x])))
'''.replace('NAME',repr(name)).replace('INITIAL',str(plan['checkpoint']['finished']['iteration'])).replace('SHA',repr(plan['source']['sha256']))
    result=json.loads(r.remote(code,timeout=35));(OUT/'live-verification.json').write_text(json.dumps(result,indent=2))
    print(r.remote("from pathlib import Path;Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch();print('Verified handoff complete')",timeout=20))
    print(json.dumps(dict(run=name,iteration=result['status']['iteration'],samples=result['status']['samples'],new_tags=result['new_tags'],replay_rows=result['replay_rows'])),flush=True)

if __name__=='__main__':
    handoff.OUT=OUT
    if sys.argv[1] in ('capture','launch'):getattr(handoff,sys.argv[1])()
    else:globals()[sys.argv[1]]()
