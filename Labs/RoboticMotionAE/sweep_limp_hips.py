"""Disposable matched-start motor-cap ablation; no cloud mutations."""
import os,sys,json
import preflight_slow_policy as p
import numpy as np,torch
from learning.base_agent import AgentMode
base=p.out/'limp-hip-audit-20261101';label=sys.argv[1];hip=float(sys.argv[2]);knee,ankle=300.,180.;out=base/label;out.mkdir(exist_ok=True)
os.chdir(p.p/'MimicKit');torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(20261102);np.random.seed(20261102);p.wp.init();p.wp.set_device('cuda:0');p.mp_util.init(0,1,'cuda:0',6759)
cfg,ec,ac=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]

env=p.SlowLocoEnv(cfg,ec,256,'cuda:0',False);agent=p.OmniPPOAgent(ac,env,'cuda:0');agent.load(str(base/'model.pt'));agent.eval();agent.set_mode(AgentMode.TEST)
mask=p.wp.to_torch(env._engine.transfer_contact.p.motor_enabled)
for motion,side in [(4,'right'),(5,'left')]:
 rows=(env._fixed_motion_ids==motion).nonzero().flatten();dofs=torch.tensor(env.disabled_dof_indices[side][:3],device='cuda:0');mask[rows[:,None],dofs[None]]=hip/200.
if len(sys.argv)>3:
 gain_scale=float(sys.argv[3]);gains=p.wp.to_torch(env._engine._uefn_motors.gains)
 for side in ['right','left']:gains[env.disabled_dof_indices[side][:3]]*=gain_scale
obs,info=env.reset();np.save(out/'initial_obs.npy',obs.cpu().numpy());ids=env._fixed_motion_ids.cpu().numpy();caps=env._engine._uefn_motors.upper.numpy()[None]*mask.cpu().numpy();alive=np.ones(256,bool);lengths=np.full(256,120);sat=np.zeros((256,34));count=np.zeros(256);max_disabled=0.;max_up=np.zeros(256);commands=np.zeros((256,34));peak_torque=np.zeros((256,34));hip_work=np.zeros(256);names=env._kin_char_model.get_body_names()
with torch.no_grad():
 for tick in range(120):
  action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action);t=abs(env._engine._dof_forces[0].cpu().numpy());sat+=(t>=.95*caps)*alive[:,None];count+=alive;commands+=(abs(action.cpu().numpy())>=.95*env._action_bound_high.cpu().numpy())*alive[:,None];peak_torque=np.maximum(peak_torque,t*alive[:,None]);max_up=np.maximum(max_up,env._engine.get_body_vel(env._get_char_id())[:,0,2].cpu().numpy()*alive)
  for motion,side in [(4,'left'),(5,'right')]:max_disabled=max(max_disabled,float(t[ids==motion][:,env.disabled_dof_indices[side]].max()))
  failed=(done.cpu().numpy()!=0)&alive;lengths[failed]=tick+1;alive[failed]=False
  reset=(done!=0).nonzero().flatten()
  if len(reset):obs,info=env.reset(reset)
report={'label':label,'knee_nm':knee,'ankle_nm':ankle,'hip_nm_per_axis':hip,'motor_gains':env._engine._uefn_motors.gains.numpy().tolist(),'action_bounds':env._action_bound_high.cpu().tolist(),'disabled_max_nm':max_disabled,'seconds_per_frame':1/30,'censor_ticks':120}
for motion,side in [(4,'right'),(5,'left')]:
 rows=ids==motion;dofs=env.disabled_dof_indices[side];report[env.motion_labels[motion]]={'first_episode_ticks':lengths[rows].tolist(),'mean_ticks':float(lengths[rows].mean()),'survived_120':int(alive[rows].sum()),'saturation_by_dof':(sat[rows][:,dofs].sum(0)/count[rows].sum()).tolist(),'command_near_bound_by_dof':(commands[rows][:,dofs].sum(0)/count[rows].sum()).tolist(),'peak_nm_by_dof':peak_torque[rows][:,dofs].max(0).tolist(),'max_pelvis_up_m_s_mean':float(max_up[rows].mean())}
(out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
