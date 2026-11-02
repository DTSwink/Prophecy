"""Guarded latest-checkpoint deployment of the validated dispatch-only candidate."""
import json,sys
from pathlib import Path
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
import resume_pushed_idle_penalty as handoff
OUT=d.OUT/'perf-lossless-20261024'/'converged-deployment'

def verify():
    plan=json.loads((OUT/'prepared.json').read_text());name=json.loads((d.OUT/'active_run.json').read_text())['run']
    assert name.endswith('uefn_locomotion_dispatch_2048')
    initial=plan['checkpoint']['finished']['iteration']
    code='''import json,time,yaml,numpy as np
from pathlib import Path
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
end=time.time()+35
while time.time()<end:
 if (p/'failure.json').exists():raise RuntimeError((p/'failure.json').read_text())
 if (p/'status.json').exists() and (p/'backup_status.json').exists():
  s=json.loads((p/'status.json').read_text())
  if s.get('iteration',0)>INITIAL+10:break
 time.sleep(3)
s=json.loads((p/'status.json').read_text());b=json.loads((p/'backup_status.json').read_text())
assert s['state']=='training' and s['iteration']>INITIAL+10 and time.time()-s['updated_unix']<180
assert not (p/'finished.json').exists() and not (p/'backup_errors.json').exists()
cfg=yaml.safe_load((p/'env_config.yaml').read_text());assert cfg['lossless_dispatch'] and cfg['perturbed_motion']['com2_loss_weight']==56.41750205477203
dispatch=json.loads((p/'lossless_dispatch.json').read_text());assert dispatch['worlds']==2048
assert dispatch['physics_kernel_intercepts']=={'velocity':8,'derivative':8} and dispatch['factor_intercepts']==16
assert dispatch['converged_newton_direction_skip'] is True and dispatch['reference_done_graphs'] is True
events=EventAccumulator(str(p));events.Reload();values=events.Scalars('loss/com2_velocity');assert values
z=np.load(p/'replay.npz');metadata=json.loads(str(z['metadata']));assert len(metadata['replay_rows'])==20
assert all(x['com2_loss']['weight']==56.41750205477203 for x in metadata['replay_rows'])
assert b['key'].split('/')[-2]==NAME
(r/'loco_ae30_handoff_complete').touch()
print(json.dumps(dict(run=NAME,status={k:s.get(k) for k in ['state','iteration','samples','worlds','training_transitions_per_second']},backup=b,dispatch=dispatch,tb_com2=values[-1].value,replay_rows=len(metadata['replay_rows']))))
'''.replace('NAME',repr(name)).replace('INITIAL',str(initial))
    result=json.loads(r.remote(code,timeout=45));(OUT/'live-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)

if __name__=='__main__':
    handoff.OUT=OUT
    if sys.argv[1] in ['stop','capture','launch']:getattr(handoff,sys.argv[1])()
    else:globals()[sys.argv[1]]()
