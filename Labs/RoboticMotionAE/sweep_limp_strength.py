"""Disposable matched-start motor-cap ablation; no cloud mutations."""
import os,sys,json
import preflight_slow_policy as p
import numpy as np,torch
from learning.base_agent import AgentMode
base=p.out/'limp-strength-update-20261101';label=sys.argv[1];knee,ankle=map(float,sys.argv[2:4]);out=base/label;out.mkdir(exist_ok=True)
os.chdir(p.p/'MimicKit');torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(20261102);np.random.seed(20261102);p.wp.init();p.wp.set_device('cuda:0');p.mp_util.init(0,1,'cuda:0',6759)
cfg,ec,ac=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
ec['uefn_motor_torque_caps_nm']={**{s+'_shin':knee for s in ['right','left']},**{s+'_foot:'+str(a):ankle for s in ['right','left'] for a in range(3)}}
env=p.SlowLocoEnv(cfg,ec,256,'cuda:0',False);agent=p.OmniPPOAgent(ac,env,'cuda:0');agent.load(str(base/'model.pt'));agent.eval();agent.set_mode(AgentMode.TEST)
obs,info=env.reset();np.save(out/'initial_obs.npy',obs.cpu().numpy());ids=env._fixed_motion_ids.cpu().numpy();caps=env._engine._uefn_motors.upper.numpy();alive=np.ones(256,bool);lengths=np.full(256,120);sat=np.zeros((256,34));count=np.zeros(256);max_disabled=0.
with torch.no_grad():
 for tick in range(120):
  action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action);t=abs(env._engine._dof_forces[0].cpu().numpy());sat+=(t>=.95*caps)*alive[:,None];count+=alive
  for motion,side in [(4,'left'),(5,'right')]:max_disabled=max(max_disabled,float(t[ids==motion][:,env.disabled_dof_indices[side]].max()))
  failed=(done.cpu().numpy()!=0)&alive;lengths[failed]=tick+1;alive[failed]=False
  reset=(done!=0).nonzero().flatten()
  if len(reset):obs,info=env.reset(reset)
report={'label':label,'knee_nm':knee,'ankle_nm':ankle,'disabled_max_nm':max_disabled,'seconds_per_frame':1/30,'censor_ticks':120}
for motion,side in [(4,'right'),(5,'left')]:
 rows=ids==motion;dofs=env.disabled_dof_indices[side];report[env.motion_labels[motion]]={'first_episode_ticks':lengths[rows].tolist(),'mean_ticks':float(lengths[rows].mean()),'survived_120':int(alive[rows].sum()),'saturation_by_dof':(sat[rows][:,dofs].sum(0)/count[rows].sum()).tolist()}
(out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
