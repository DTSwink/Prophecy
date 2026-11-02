"""Matched-phase policy/servo diagnostics; local disposable simulations only."""
import os,json
import preflight_slow_policy as p
import numpy as np,torch,mujoco
from scipy.spatial.transform import Rotation as R
from learning.base_agent import AgentMode
from repair_slow_targets import Geometry
from util import torch_util as qu

out=p.out/'limp-deep-audit-20261101';g=Geometry()
os.chdir(p.p/'MimicKit');torch.set_num_threads(2);torch.set_num_interop_threads(1);p.wp.init();p.wp.set_device('cuda:0');p.mp_util.init(0,1,'cuda:0',6766)
cfg,ec,ac=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
env=p.SlowLocoEnv(cfg,ec,256,'cuda:0',False);e=env._engine;c=env._get_char_id();agent=p.OmniPPOAgent(ac,env,'cuda:0');agent.eval();agent.set_mode(AgentMode.TEST)
mujoco.mj_saveModel(e._solver.mj_model,str(out/'actual-model.mjb'))
ids=env._fixed_motion_ids.cpu().numpy();rows=np.flatnonzero((ids==4)|(ids==5));rt=torch.tensor(rows,device='cuda:0');n=len(rows)
mask=p.wp.to_torch(e.transfer_contact.p.motor_enabled);original_mask=mask.clone()
mass=e._sim_model.body_mass.numpy().reshape(256,15)[0].copy();offset=e._sim_model.body_com.numpy().reshape(256,15,3)[0].copy()
def body_measure(pos,quat):
    rot=R.from_quat(quat.reshape(-1,4)).as_matrix().reshape(-1,15,3,3);com=np.einsum('nbi,b->ni',pos+np.einsum('nbij,bj->nbi',rot,offset),mass)/mass.sum()
    gp=pos[:,g.gb]+np.einsum('ngij,gj->ngi',rot[:,g.gb],g.gp);gr=rot[:,g.gb]@g.gr
    bottoms=np.array([gp[:,j,2]-(np.abs(gr[:,j,2])@geom['size'] if geom['type']=='box' else geom['size'][0]+abs(gr[:,j,2,2])*geom['size'][1]) for j,geom in enumerate(g.gs)]).T
    feet=np.stack([bottoms[:,g.gb==b].min(1) for b in (11,14)],1)
    return com,feet
# Dense exact runtime reference, including velocities and generalized state.
for motion in (4,5):
    times=torch.arange(280,device='cuda:0')/240;mid=torch.full((280,),motion,device='cuda:0',dtype=torch.long)
    root,rot,vel,ang,joints,dof=env._motion_lib.calc_motion_frame(mid,times)
    pos,brot=env._kin_char_model.forward_kinematics(root,rot,joints);bv,ba=env._world_reference_velocities(pos,brot,vel,ang,dof,mid,times)
    com,feet=body_measure(pos.cpu().numpy(),brot.cpu().numpy());frame=torch.cat([root,qu.quat_to_exp_map(rot),env._motion_lib.joint_rot_to_dof(joints)],-1)
    np.savez_compressed(out/(env.motion_labels[motion]+'-reference.npz'),times=times.cpu().numpy(),frames=frame.cpu().numpy(),pos=pos.cpu().numpy(),quat=brot.cpu().numpy(),vel=bv.cpu().numpy(),ang=ba.cpu().numpy(),com=com,feet=feet,joint_quat=joints.cpu().numpy(),root_quat=rot.cpu().numpy())
cases=[('policy9189',p.out/'limp-strength-update-20261101/model.pt',0,False,1),('policy9597',out/'model.pt',0,False,1),('servo15',None,15,False,1),('servo40',None,40,False,1),('servo40_hip3',None,40,False,3),('servo40_bothlegs',None,40,True,1)]
summary={}
with torch.no_grad():
 for label,model,kp,enable,hipscale in cases:
    mask.copy_(original_mask)
    for motion,support,disabled in [(4,'right','left'),(5,'left','right')]:
        rr=(env._fixed_motion_ids==motion).nonzero().flatten()
        if enable:mask[rr[:,None],torch.tensor(env.disabled_dof_indices[disabled],device='cuda:0')[None]]=1
        mask[rr[:,None],torch.tensor(env.disabled_dof_indices[support][:3],device='cuda:0')[None]]=hipscale
    if model:agent.load(str(model))
    torch.manual_seed(20261105);obs,info=env.reset();initial=obs.cpu().numpy().copy();initial_phase=(env._get_motion_times()/env._motion_lib.get_motion_length(env._motion_ids)).remainder(1)[rt].cpu().numpy();data={k:[] for k in ['pos','quat','com','feet','target_com','target_feet','body_losses','losses','reward','done','command','torque','qvel','phase','target_distance','vel','target_vel']}
    for tick in range(90):
        if model:action,_=agent._decide_action(obs,info)
        else:
            values=env._motion_lib.calc_motion_frame(env._motion_ids,env._get_motion_times()+1/30)
            cur=env._kin_char_model.dof_to_rot(e.get_dof_pos(c));action=env._kin_char_model.compute_dof_vel(cur,values[4],1/kp)+values[5]
        obs,reward,done,info=env.step(action)
        pos=e.get_body_pos(c)[rt];rot=e.get_body_rot(c)[rt];ang=e.get_body_ang_vel(c)[rt];vel=e.get_body_vel(c)[rt]-torch.cross(ang,qu.quat_rotate(rot,env._body_com[rt]),dim=-1)
        tp=env.reward_target_pos[rt];tr=env.reward_target_rot[rt];tv=env.reward_target_vel[rt];ta=env.reward_target_ang[rt]
        bodyloss=torch.stack([(pos-tp).square().mean(-1),(vel-tv).square().mean(-1),(qu.quat_to_matrix(rot)-qu.quat_to_matrix(tr)).square().mean((-1,-2)),(ang-ta).square().mean(-1)],-1)*env._loss_weights/15
        com,feet=body_measure(pos.cpu().numpy(),rot.cpu().numpy());tc,tf=body_measure(tp.cpu().numpy(),tr.cpu().numpy())
        values=[pos,rot,com,feet,tc,tf,bodyloss,env.loss_terms[rt],reward[rt],done[rt],action[rt],e._dof_forces[0][rt],e.get_dof_vel(c)[rt],env._command_phase()[1][rt],env.target_distances_sq[rt].sqrt(),vel,tv]
        for key,value in zip(data,values):data[key].append(value.cpu().numpy().copy() if isinstance(value,torch.Tensor) else value.copy())
    data={k:np.array(v) for k,v in data.items()};np.savez_compressed(out/(label+'.npz'),**data,motion_ids=ids[rows],initial_phase=initial_phase,initial_obs=initial)
    result={}
    for motion in (4,5):
        ii=np.flatnonzero(ids[rows]==motion);fail=data['done'][:,ii]!=0;length=np.where(fail.any(0),fail.argmax(0)+1,90);valid=np.arange(90)[:,None]<length[None]
        loss=data['body_losses'][:,ii][valid];bodies=loss.sum(2).mean(0);passive=[12,13,14] if motion==4 else [9,10,11]
        activefoot=0 if motion==4 else 1;ah=data['feet'][:,ii,activefoot];th=data['target_feet'][:,ii,activefoot];miss=((th>.02)&(ah<.01)&valid)
        result[env.motion_labels[motion]]=dict(mean_first_fail_ticks=float(length.mean()),median_first_fail_ticks=float(np.median(length)),survived90=int((length==90).sum()),mean_reward=float(data['reward'][:,ii][valid].mean()),mean_loss=float(data['losses'][:,ii][valid].sum(1).mean()),loss_by_body=dict(zip(g.names,bodies.tolist())),passive_loss_fraction=float(bodies[passive].sum()/bodies.sum()),target_swing_missed_fraction=float(miss.sum()/max(1,((th>.02)&valid).sum())),com_z_rmse_cm=float(np.sqrt(((data['com'][:,ii,2]-data['target_com'][:,ii,2])[valid]**2).mean())*100))
    summary[label]=result;(out/'tracking-summary.json').write_text(json.dumps(summary,indent=2));print('TRACKING '+json.dumps({label:result}),flush=True)
