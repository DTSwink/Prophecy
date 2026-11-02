"""Independent 240 Hz verification, passive-leg clearance and motors-off controls."""
import os,json,sys
import preflight_slow_policy as p
import numpy as np,torch
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry

source=p.out/'limp-mechanical-capacity-20261101'
knee_cap=float(sys.argv[1]) if len(sys.argv)>1 else 300.
out=(p.out/'knee-capacity-20261101'/('knee'+str(int(knee_cap)))) if len(sys.argv)>1 else source
out.mkdir(parents=True,exist_ok=True);g=Geometry()
os.chdir(p.p/'MimicKit');torch.set_num_threads(2);torch.set_num_interop_threads(1)
p.wp.init();p.wp.set_device('cuda:0');p.mp_util.init(0,1,'cuda:0',6764)
cfg,ec=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine')]
env=p.SlowLocoEnv(cfg,ec,64,'cuda:0',False);e=env._engine;c=env._get_char_id();env.reset()
ids=env._fixed_motion_ids.cpu().numpy();rows=np.flatnonzero((ids==4)|(ids==5));rt=torch.tensor(rows,device='cuda:0');n=len(rows)
mass=e._sim_model.body_mass.numpy().reshape(64,15)[0].copy();offset=e._sim_model.body_com.numpy().reshape(64,15,3)[0].copy()
frames=[];params=[];sd=[];dd=[];groups=[];audit=[]
counts={4:0,5:0}
for row in rows:
    name=env.motion_labels[ids[row]];d=np.load(source/(name+'-best.npz'));f=d['initial_frame'].copy();group=counts[ids[row]]%4;counts[ids[row]]+=1
    if group>=2:
        f[6+d['disabled'][3]]+=.9;f[6+d['disabled'][4:]]=0
    g.set_pose(*g.fk(f));audit.append(dict(row=int(row),motion=name,group=group,lowest_m=float(g.floors().min()),limits=g.limits(f),self_collision_min_m=float(g.distances(f).min())))
    frames.append(f);params.append(d['params']);sd.append(d['support']);dd.append(d['disabled']);groups.append(group)
frames=np.array(frames);params=np.array(params);sd=np.array(sd);dd=np.array(dd);groups=np.array(groups)
e.set_root_pos(rt,c,torch.tensor(frames[:,:3],device='cuda:0',dtype=torch.float32));e.set_root_rot(rt,c,torch.tensor(R.from_rotvec(frames[:,3:6]).as_quat(),device='cuda:0',dtype=torch.float32))
e.set_dof_pos(rt,c,torch.tensor(frames[:,6:],device='cuda:0',dtype=torch.float32));e.set_root_vel(rt,c,0.);e.set_root_ang_vel(rt,c,0.);e.set_dof_vel(rt,c,0.)
e._sim_state.pre_step_update();e._sim_state.eval_fk();e._body_velocity.update(e._sim_state.raw_state)
mask=p.wp.to_torch(e.transfer_contact.p.motor_enabled)
for motion,side in [(4,'right'),(5,'left')]:
    worlds=(env._fixed_motion_ids==motion).nonzero().flatten();knee=env.disabled_dof_indices[side][3];mask[worlds,knee]=knee_cap/float(e._uefn_motors.upper.numpy()[knee])
mask[rt[torch.tensor(groups%2==1,device='cuda:0')]]=0
caps=e._uefn_motors.upper.numpy()[None]*mask.cpu().numpy()[rows]
q0=e.get_dof_pos(c).clone();target=q0.clone();vals=frames[:,6:][np.arange(n)[:,None],sd].copy();vals[:,2]=params[:,0];vals[:,3]=params[:,1];vals[:,4:]=params[:,2:5]
target[rt[:,None],torch.tensor(sd,device='cuda:0')]=torch.tensor(vals,device='cuda:0',dtype=torch.float32)
gain=torch.ones((64,1),device='cuda:0')*12;gain[rt]=torch.tensor(params[:,5:6],device='cuda:0',dtype=torch.float32)
# Same eight physics substeps per 30 Hz command, read each substep independently.
e._graph=None;e._sim_steps=1
data={key:[] for key in ('com','velocity','feet','floor','force','torque','qvel','pos','quat')}
def capture():
    pos=e.get_body_pos(c)[rt].cpu().numpy().copy();quat=e.get_body_rot(c)[rt].cpu().numpy().copy();rot=R.from_quat(quat.reshape(-1,4)).as_matrix().reshape(n,15,3,3)
    com=np.einsum('nbi,b->ni',pos+np.einsum('nbij,bj->nbi',rot,offset),mass)/mass.sum()
    vel=np.einsum('nbi,b->ni',e.get_body_vel(c)[rt].cpu().numpy(),mass)/mass.sum()
    gp=pos[:,g.gb]+np.einsum('ngij,gj->ngi',rot[:,g.gb],g.gp);gr=rot[:,g.gb]@g.gr;bottom=[]
    for j,geom in enumerate(g.gs):
        s=geom['size'];extent=np.abs(gr[:,j,2])@s if geom['type']=='box' else s[0]+abs(gr[:,j,2,2])*s[1];bottom.append(gp[:,j,2]-extent)
    bottom=np.array(bottom).T;feet=np.stack([bottom[:,g.gb==g.names.index(side+'_foot')].min(1) for side in ('right','left')],1)
    values=(com,vel,feet,bottom.min(1),e.get_ground_contact_forces(c)[rt].cpu().numpy().copy(),e._dof_forces[0][rt].cpu().numpy().copy(),e.get_dof_vel(c)[rt].cpu().numpy().copy(),pos,quat)
    for key,value in zip(data,values):data[key].append(value)
capture()
for tick in range(24):
    q=e.get_dof_pos(c);action=(target-q)*gain;after=torch.tensor(tick>=params[:,6],device='cuda:0');action[rt[after]]=(q0[rt[after]]-q[rt[after]])*10
    action=torch.minimum(torch.maximum(action,env._action_bound_low),env._action_bound_high);e.set_cmd(c,action)
    for sub in range(8):e.step();capture()
data={k:np.array(v) for k,v in data.items()};reports=[]
for i,row in enumerate(rows):
    air=(data['feet'][:,i].min(1)>.01)&(data['floor'][:,i]>.005);ticks=np.flatnonzero(air)
    sb=11 if ids[row]==4 else 14;db=14 if ids[row]==4 else 11
    torque=data['torque'][1:,i];work=np.sum(torque*data['qvel'][1:,i],axis=1)/240
    reports.append(dict(row=int(row),motion=env.motion_labels[ids[row]],group=['authored_powered','authored_motors_off','single_foot_powered','single_foot_motors_off'][groups[i]],initial_velocity_m_s=data['velocity'][0,i].tolist(),max_up_speed_m_s=float(data['velocity'][:,i,2].max()),com_rise_m=float(data['com'][:,i,2].max()-data['com'][0,i,2]),airborne_start_s=float(ticks[0]/240) if len(ticks) else None,airborne_end_s=float(ticks[-1]/240) if len(ticks) else None,airborne_samples=len(ticks),max_both_feet_clearance_m=float(data['feet'][:,i].min(1).max()),disabled_peak_torque_nm=float(abs(torque[:,dd[i]]).max()),support_peak_torque_nm=abs(torque[:,sd[i]]).max(0).tolist(),torque_over_cap_nm=float((abs(torque)-caps[i]).max()),positive_motor_work_j=float(np.maximum(work,0).sum()),ground_force_peak_n=float(data['force'][1:,i,:,2].sum(1).max()),support_impulse_ns=float(data['force'][1:49,i,sb,2].sum()/240),disabled_impulse_ns=float(data['force'][1:49,i,db,2].sum()/240),disabled_min_height_first_200ms_m=float(data['feet'][:49,i,1 if ids[row]==4 else 0].min()),initial_geometry=audit[i]))
np.savez_compressed(out/'verification-trajectories.npz',**data,rows=rows,groups=groups,motion_ids=ids[rows],mass=mass,initial_frames=frames)
(out/'verification.json').write_text(json.dumps(dict(dt=1/240,mass_kg=float(mass.sum()),support_knee_cap_nm=knee_cap,reports=reports),indent=2));print(json.dumps(reports,indent=2),flush=True)
