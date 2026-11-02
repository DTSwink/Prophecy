"""Read-only checks of the unchanged locomotion resume; release setup guard on success."""
import json
from pathlib import Path

import deploy_locomotion_branch as d
import restart_locomotion_ae as r


def main():
    active = json.loads((d.OUT / 'active_run.json').read_text())
    plan = json.loads((d.OUT / 'getup-success-prepared.json').read_text())
    assert 'uefn_locomotion_leg7_idle3_2048' in active['run']
    assert active['pod'] == d.cloud.state()['pod_id']
    code = '''from pathlib import Path
import json,time,hashlib,zipfile,yaml,numpy as np
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
end=time.time()+40
while time.time()<end:
 if (p/'failure.json').exists():raise RuntimeError((p/'failure.json').read_text())
 if (p/'status.json').exists() and (p/'backup_status.json').exists():
  s=json.loads((p/'status.json').read_text())
  if s.get('iteration',0)>=INITIAL:break
 time.sleep(3)
if not (p/'status.json').exists() or not (p/'backup_status.json').exists():
 print(json.dumps(dict(ready=False,log=(r/(NAME+'.log')).read_text()[-900:])));raise SystemExit
s=json.loads((p/'status.json').read_text())
if s.get('iteration',0)<INITIAL:
 print(json.dumps(dict(ready=False,iteration=s.get('iteration'))));raise SystemExit
assert s['state']=='training' and time.time()-s['updated_unix']<120
assert not any((p/n).exists() for n in ['failure.json','numerical_failure.json','backup_errors.json','finished.json'])
assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==SOURCE
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==CHECKPOINT
with zipfile.ZipFile(r/'resume.zip') as cp:
 for name in ['engine_config.yaml','agent_config.yaml']:
  assert yaml.safe_load(cp.read(name))==yaml.safe_load((p/name).read_text()),name
with zipfile.ZipFile(r/'source.zip') as source:
 assert yaml.safe_load(source.read('prepared/env_config.yaml'))==yaml.safe_load((p/'env_config.yaml').read_text())
assert yaml.safe_load((p/'env_config.yaml').read_text())['perturbed_motion']['idle_minus_min_fraction']==.03
dispatch=json.loads((p/'lossless_dispatch.json').read_text())
assert dispatch['worlds']==2048 and dispatch['reference_done_graphs']
assert dispatch['physics_kernel_intercepts']==dict(velocity=8,derivative=8)
assert dispatch['factor_intercepts']==16 and dispatch['cached_cholesky_intercepts']==16
z=np.load(p/'replay.npz');rows=json.loads(str(z['metadata']))['replay_rows']
for i,row in enumerate(rows):
 assert all(n in row['loss_term_names'] for n in ['excessive_stepping','foot_linear_reversal','foot_angular_reversal','head_reversal','com2_velocity','leg_reversal'])
 assert row['frame_com2_reward_multiplier']
 assert np.isfinite(z['loss_terms'+('' if i==0 else '_'+str(i))]).all()
b=json.loads((p/'backup_status.json').read_text())
assert b.get('verified_unix',0)>0
assert hashlib.sha256((p/Path(b['key']).name).read_bytes()).hexdigest()==b['sha256']
resume=json.loads((p/'resume.json').read_text())
print(json.dumps(dict(ready=True,run=NAME,status={k:s.get(k) for k in ['state','iteration','samples','updated_unix','recent_iteration_mean_seconds','training_transitions_per_second']},backup=b,replay_rows=len(rows),resume=resume,source_sha256=SOURCE,config_match=True,dispatch=dispatch)))
'''.replace('INITIAL',str(plan['checkpoint']['finished']['iteration']+10)).replace('NAME', repr(active['run'])).replace('SOURCE', repr(plan['source']['sha256'])).replace('CHECKPOINT', repr(plan['checkpoint']['sha256']))
    result = json.loads(r.remote(code, timeout=75))
    out = d.OUT / 'leg-losses-20261028'
    (out / 'live-verification.json').write_text(json.dumps(result, indent=2))
    if result['ready']:
        (out / 'retry-verified').touch()
        (d.OUT / 'setup-verified').touch()
        r.remote("from pathlib import Path; Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch()")
        (d.OUT / 'funds-resume-verified').touch()
    print(json.dumps({k: v for k, v in result.items() if k not in ('resume', 'dispatch')}), flush=True)


if __name__ == '__main__':
    main()
