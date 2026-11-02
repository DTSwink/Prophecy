"""Bounded GPU correctness and throughput check; frozen production checkpoint."""
import os,sys,json,time,zipfile,io
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
os.environ['PYGLET_HEADLESS']='true'
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import torch,warp as wp,yaml
from util import mp_util
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from envs.base_env import EnvMode
from resume import restore,migrate_physical_observation_scales

torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',2026102380)
os.chdir(ROOT/'MimicKit')
cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False);env.reset();f=env._final;e=env._engine;c=env._get_char_id()
assert int(env._perturbed_rows.sum())==717 and int(f.plus.sum())==502 and int(f.pushed.sum())==215
normal_idle=int((~env._perturbed_rows & (env._gaits[env._fixed_motion_ids]==-1)).sum());assert int(f.minus.sum())==round(normal_idle*.5)
print('cohorts',int(f.pushed.sum()),int(f.plus.sum()),normal_idle,int(f.minus.sum()),flush=True)
# Verify reset picks the exact baked states and independent velocity frames.
for prefix,mask in [('push',f.pushed),('plus',f.plus)]:
 rows=torch.where(mask)[0];index=(env._motion_ids[rows],f.choice[rows]) if prefix=='push' or f.cfg.get('plus_blended') else f.choice[rows]
 for field,actual in [('dof',e.get_dof_pos(c)),('dof_vel',e.get_dof_vel(c)),('root_rot',e.get_root_rot(c)),('root_ang',e.get_root_ang_vel(c))]:
  torch.testing.assert_close(actual[rows],f.bank[prefix+'_'+field][index].float(),atol=2e-5,rtol=2e-5)
# Synchronized kicks at exact ticks; verify actual body COM velocity change.
env._time_buf[f.pushed]=79/30;env._time_buf[f.minus]=(int(f.cfg.get('minus_kick_interval',30))-1)/30
ids=[env._kin_char_model.get_body_names().index(n) for n in ['right_hand','left_hand','right_foot','left_foot','pelvis']]
before=e.get_body_vel(c)[:,ids,:2].clone();position=e.get_body_pos(c).clone()
started=time.perf_counter();f.before_step();torch.cuda.synchronize();kick_seconds=time.perf_counter()-started
rows=torch.where(f.pushed|f.minus)[0]
torch.testing.assert_close(e.get_body_pos(c),position,atol=3e-4,rtol=2e-5)
measured=e.get_body_vel(c)[rows][:,ids,:2]-before[rows]
torch.testing.assert_close(measured,f.last_requested[rows],atol=.002,rtol=.001)
kick_error=float((measured-f.last_requested[rows]).abs().max())
assert (f.last_kick[f.pushed]==80).all() and (f.last_kick[f.minus]==int(f.cfg.get('minus_kick_interval',30))).all()
# Counter gates: once latched, it is not reset by a later lifted foot.
f.first_foot[f.plus]=10
boundary=10+int(f.cfg.get('plus_foot_grace',40))
t=torch.full_like(env._time_buf,boundary-1);gate=f.velocity_gate(t);assert not gate[f.plus].any()
t[:]=boundary;gate=f.velocity_gate(t);assert gate[f.plus].all()
t[:]=129;gate=f.velocity_gate(t);assert not gate[f.pushed].any()
t[:]=130;gate=f.velocity_gate(t);assert gate[f.pushed].all()
with zipfile.ZipFile(ROOT/'resume.zip') as z:ac=yaml.safe_load(z.read('agent_config.yaml'))
agent=OmniPPOAgent(ac,env,'cuda:0');restore(agent,ROOT/'resume.zip');migrate_physical_observation_scales(agent)
agent.eval();agent.set_mode(AgentMode.TEST);env.set_mode(EnvMode.TEST);env.reset()
times=[];counts=0
with torch.inference_mode():
 for tick in range(160):
  start=time.perf_counter();obs=env._compute_obs();norm=agent._obs_norm.normalize(obs)
  action=agent._a_norm.unnormalize(agent._model.eval_actor(norm).mode)
  env.queue_phase_prediction(agent._model.eval_phase(norm[env._phase_feedback_ids]));env.step(action)
  assert torch.isfinite(env._reward_buf).all()
  done=torch.where(env._done_buf!=0)[0];counts+=len(done)
  if len(done):env.reset(done)
  torch.cuda.synchronize();times.append(time.perf_counter()-start)
report=dict(passed=True,worlds=1024,normal=307,perturbed=215,plus=502,idle_minus=int(f.minus.sum()),
  bank_reset_verified=True,kick_error_m_s=kick_error,kick_first_call_seconds=kick_seconds,
  velocity_gate_boundaries=True,frozen_rollout_ticks=160,episodes=counts,
  rollout_transitions_per_second=1024/(sum(times[10:])/len(times[10:])))
(ROOT/'final-phase-preflight.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
