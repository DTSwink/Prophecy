import os,sys,json,time,pickle,xml.etree.ElementTree as ET
from pathlib import Path
import preflight_slow_policy as p
import torch,numpy as np
from learning.base_agent import AgentMode
base=p.out/'limp-strength-20261101';factor=float(sys.argv[1]) if len(sys.argv)>1 else 1.;out=base/('caps'+str(factor));out.mkdir(exist_ok=True);torch.manual_seed(20261101);np.random.seed(20261101)
os.chdir(p.p/'MimicKit');torch.set_num_threads(2);torch.set_num_interop_threads(1);p.wp.init();p.wp.set_device('cuda:0');p.mp_util.init(0,1,'cuda:0',6758)
cfg,ec,ac=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
if factor>1:ec['uefn_motor_torque_caps_nm']={**{side+'_shin':150*factor for side in ['right','left']},**{side+'_foot:'+str(axis):90*factor for side in ['right','left'] for axis in range(3)}}
env=p.SlowLocoEnv(cfg,ec,64,'cuda:0',False);agent=p.OmniPPOAgent(ac,env,'cuda:0');agent.load(str(base/'model.pt'));agent.eval();agent.set_mode(AgentMode.TEST)
engine=env._engine;caps=engine._uefn_motors.upper.numpy();names=env._kin_char_model.get_body_names();report={'caps':caps.tolist(),'motor_parameter_fields':[n for n in dir(engine.transfer_contact.p) if 'motor' in n]}
print(json.dumps(report),flush=True)
obs,info=env.reset();torques=[];vels=[];positions=[];dones=[];distances=[]
with torch.no_grad():
 for tick in range(300):
  action,_=agent._decide_action(obs,info);obs,r,done,info=env.step(action)
  torques.append(engine._dof_forces[0].cpu().numpy().copy());vels.append(engine.get_body_vel(env._get_char_id()).cpu().numpy().copy());positions.append(engine.get_body_pos(env._get_char_id()).cpu().numpy().copy());dones.append(done.cpu().numpy().copy());distances.append(env.target_distances_sq.sqrt().cpu().numpy().copy())
  ids=(done!=0).nonzero().flatten()
  if len(ids):obs,info=env.reset(ids)
ids=env._fixed_motion_ids.cpu().numpy();t=np.array(torques);v=np.array(vels);pos=np.array(positions);ds=np.array(dones)
np.savez_compressed(out/'policy-probe.npz',torques=t,velocities=v,positions=pos,done=ds,distances=np.array(distances),motion_ids=ids,caps=caps)
for motion,side,disabled in [(4,'right','left'),(5,'left','right')]:
 rows=ids==motion;dofs=env.disabled_dof_indices[side];td=t[:,rows][:,:,dofs];ratio=abs(td)/caps[dofs]
 lens=[]
 for row in np.where(rows)[0]:
  ends=np.where(ds[:,row]!=0)[0];lens.extend(np.diff(np.r_[-1,ends]).tolist())
 report[env.motion_labels[motion]]={'enabled_dofs':dofs,'saturation_fraction_each_dof':(ratio>=.95).mean(axis=(0,1)).tolist(),'peak_nm_each_dof':abs(td).max(axis=(0,1)).tolist(),'any_enabled_leg_motor_saturated_fraction':float((ratio>=.95).any(axis=2).mean()),'disabled_torque_max':float(abs(t[:,rows][:,:,env.disabled_dof_indices[disabled]]).max()),'completed_episode_ticks_mean':float(np.mean(lens)),'episodes':len(lens),'first_episode_ticks_each_row':[int(np.where(ds[:,row]!=0)[0][0]+1) if (ds[:,row]!=0).any() else 300 for row in np.where(rows)[0]],'pelvis_up_velocity_p95_max':np.percentile(v[:,rows,names.index('pelvis'),2],[95,100]).tolist(),'failure_point_counts':((np.array(distances)[:,rows]>np.sqrt(env._target_radii_sq.cpu().numpy()[rows])[None])*env._target_termination_enabled.cpu().numpy()[rows][None]).sum(axis=(0,1)).tolist()}
(out/'policy-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
