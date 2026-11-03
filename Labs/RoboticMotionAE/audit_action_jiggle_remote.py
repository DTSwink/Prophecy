import os,sys,json,time
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
r=Path('/workspace/mimickit_trial');sys.path[:0]=[str(r/'pipeline'),str(r/'MimicKit/mimickit')]
import torch,numpy as np,yaml,warp as wp
from slow_loco_disabled import DisabledSlowLocoEnv
from omni_policy import OmniPPOAgent
from resume import restore
from learning.base_agent import AgentMode
from util import mp_util
torch.set_num_threads(2);os.chdir(r/'MimicKit');wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6785)
cfg,ec,ac=[yaml.safe_load((r/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
env=DisabledSlowLocoEnv(cfg,ec,64,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
pin=json.loads((r/'action-audit-resume.json').read_text());restore(agent,pin['path']);agent.eval();agent.set_mode(AgentMode.TEST)
obs,info=env.reset();actions=[];dones=[];poses=[];streak=[]
with torch.no_grad():
 for t in range(300):
  mean=agent._model.eval_actor(agent._obs_norm.normalize(obs)).mode
  action=agent._a_norm.unnormalize(mean);actions.append(mean.cpu().numpy());poses.append(env._engine.get_body_rot(env._get_char_id()).cpu().numpy())
  obs,rew,done,info=env.step(action);dones.append(done.cpu().numpy());streak.append(env._jiggle_termination.streak.cpu().numpy())
  obs,info=env.reset((done!=0).nonzero().flatten())
scale=agent._a_norm.get_std().cpu().numpy()
np.savez_compressed(r/'action-audit.npz',mean=np.asarray(actions),done=np.asarray(dones),rotation=np.asarray(poses),streak=np.asarray(streak),motor_mask=env._motor_enabled_binary.cpu().numpy(),scale=scale,reference_velocity=env._motion_lib._frame_dof_vel.cpu().numpy())
print('ACTION AUDIT COMPLETE',flush=True)
