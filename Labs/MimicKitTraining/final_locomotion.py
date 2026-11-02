"""Opt-in final locomotion curriculum; immutable CPU-baked initialization bank."""
import hashlib
from pathlib import Path
import numpy as np
import torch
import warp as wp
import mujoco_warp as mjw
from walking_airborne import foot_box_bottoms


def stratified_subset(ids, groups, count, n, device):
    result=torch.zeros(n,dtype=torch.bool,device=device)
    keys=torch.unique(groups[ids]);rows=[ids[groups[ids]==k] for k in keys]
    exact=np.array([len(r)*count/max(len(ids),1) for r in rows]);counts=np.floor(exact).astype(int)
    counts[np.argsort(-(exact-counts),kind='stable')[:count-int(counts.sum())]]+=1
    for r,c in zip(rows,counts):
        if c:result[r[torch.floor((torch.arange(int(c),device=device)+.5)*len(r)/int(c)).long()]]=True
    return result


class FinalLocomotion:
    def __init__(self,env,cfg):
        self.env=env;self.cfg=cfg;dev=env._device;n=env.get_num_envs()
        path=Path(cfg['initializations'])
        assert hashlib.sha256(path.read_bytes()).hexdigest()==cfg['sha256']
        with np.load(path,allow_pickle=False) as z:
            assert z['body_names'].tolist()==env._kin_char_model.get_body_names()
            self.bank={k:torch.as_tensor(z[k].copy(),device=dev) for k in z.files if k!='body_names'}
        ids=env._perturbed_ids
        self.plus=stratified_subset(ids,env._fixed_motion_ids,round(len(ids)*.7),n,dev)
        self.pushed=env._perturbed_rows & ~self.plus
        idle=torch.where(~env._perturbed_rows & (env._gaits[env._fixed_motion_ids]==-1))[0]
        self.minus=stratified_subset(idle,env._fixed_motion_ids,round(len(idle)*.5),n,dev)
        env._pose_termination_mask = ~self.minus
        self.choice=torch.zeros(n,dtype=torch.long,device=dev)
        self.kick_choice=torch.zeros_like(self.choice)
        self.first_foot=torch.full_like(self.choice,-1)
        self.last_kick=torch.full_like(self.choice,-1)
        self.kick_count=torch.zeros_like(self.choice)
        self.kick_error=torch.zeros(n,device=dev)
        self.last_requested=torch.zeros(n,5,2,device=dev)
        self.kicker=None

    def reference(self,ids):
        e=self.env;push=ids[self.pushed[ids]];plus=ids[self.plus[ids]]
        self.choice[push]=torch.randint(self.bank['push_dof'].shape[1],(len(push),),device=e._device)
        self.choice[plus]=torch.randint(self.bank['plus_dof'].shape[1] if self.cfg.get('plus_blended') else len(self.bank['plus_dof']),(len(plus),),device=e._device)
        self.kick_choice[ids]=torch.randint(len(self.bank['kicks']),(len(ids),),device=e._device)
        self.first_foot[ids]=-1;self.last_kick[ids]=-1;self.kick_count[ids]=0;self.kick_error[ids]=0;self.last_requested[ids]=0
        for prefix,rows in [('push',push)]+([('plus',plus)] if self.cfg.get('plus_blended') else []):
            m=e._motion_ids[rows];t=self.bank[prefix+'_motion_time'][m,self.choice[rows]]
            e._motion_time_offsets[rows]=t
            values=e._motion_lib.calc_motion_frame(m,t)
            for dest,value in zip((e._ref_root_pos,e._ref_root_rot,e._ref_root_vel,e._ref_root_ang_vel,e._ref_joint_rot,e._ref_dof_vel),values):dest[rows]=value
            e._ref_dof_pos[rows]=e._motion_lib.joint_rot_to_dof(values[4])
            p,q=e._kin_char_model.forward_kinematics(values[0],values[1],values[4]);e._ref_body_pos[rows]=p;e._ref_body_rot[rows]=q

    def reset_state(self,ids):
        env=self.env;e=env._engine;char=env._get_char_id()
        for prefix,mask in [('push',self.pushed),('plus',self.plus)]:
            rows=ids[mask[ids]];choice=self.choice[rows]
            index=(env._motion_ids[rows],choice) if prefix=='push' or self.cfg.get('plus_blended') else choice
            for field,setter in [('root_pos',e.set_root_pos),('root_rot',e.set_root_rot),('root_vel',e.set_root_vel),('root_ang',e.set_root_ang_vel),('dof',e.set_dof_pos),('dof_vel',e.set_dof_vel)]:
                value=self.bank[prefix+'_'+field][index].float()
                if prefix=='plus' and field=='root_pos':
                    value=value.clone();value[:,:2]=e.get_root_pos(char)[rows,:2]
                setter(rows,char,value)
            env._random_pose_frame[rows]=self.bank[prefix+'_joint_frame'][index]
            if prefix=='push':env._yaw_degrees[rows]=self.bank['push_yaw_degrees'][index]

    def before_step(self):
        e=self.env;t=torch.round(e._time_buf*30).long()+1
        interval=int(self.cfg.get('minus_kick_interval',30))
        due=(self.pushed & (t==80)) | (self.minus & (t>0) & (t%interval==0))
        rows=torch.where(due)[0]
        if not len(rows):return
        slot=torch.where(self.pushed[rows],0,t[rows]//interval-1).clamp_max(self.bank['kicks'].shape[1]-1)
        desired=self.bank['kicks'][self.kick_choice[rows],slot].float()
        if self.kicker is None:self.kicker=ArticulatedKicks(e._engine)
        error=self.kicker.apply(rows,desired)
        self.last_kick[rows]=t[rows];self.kick_count[rows]+=1;self.kick_error[rows]=error;self.last_requested[rows]=desired

    def velocity_gate(self,ticks):
        e=self.env;engine=e._engine;c=e._get_char_id();ids=e._walking_foot_ids
        bottom=foot_box_bottoms(engine.get_body_pos(c)[:,ids],engine.get_body_rot(c)[:,ids],e._walking_foot_centers,e._walking_foot_half_axes).amin(-1)
        contact=self.plus & (self.first_foot<0) & (bottom<.01)
        self.first_foot.copy_(torch.where(contact,ticks.long(),self.first_foot))
        return (self.pushed & ((ticks<80) | (ticks>=130))) | (self.plus & (self.first_foot>=0) & (ticks>=self.first_foot+int(self.cfg.get('plus_foot_grace',40))))

    def replay_worlds(self, selected, selection_round):
        # Keep two idle examples, while showing every locomotion cohort.
        e=self.env;groups={};idle={}
        motions=e._fixed_motion_ids.cpu().tolist();gaits=e._gaits.cpu().tolist()
        equipment=e._equipment.cpu().tolist()
        plus=self.plus.cpu().tolist();pushed=self.pushed.cpu().tolist();minus=self.minus.cpu().tolist()
        for w,m in enumerate(motions):
            cohort=2 if plus[w] else 1 if pushed[w] else 3 if minus[w] else 0
            if gaits[m]==-1:idle.setdefault(cohort,[]).append(w)
            else:groups.setdefault((cohort,gaits[m],bool(equipment[m])),[]).append(w)
        result=[]
        if 3 in idle:result.append(idle[3][selection_round%len(idle[3])])
        others=[k for k in sorted(idle) if k!=3]
        if others:
            v=idle[others[selection_round%len(others)]];result.append(v[selection_round%len(v)])
        for v in groups.values():result.append(v[selection_round%len(v)])
        for w in selected+list(range(len(motions))):
            if len(result)>=len(selected):break
            if gaits[motions[w]]!=-1 and w not in result:result.append(w)
        return result[:len(selected)]

    def metadata(self,world,result):
        cohort='perturbed+' if self.plus[world] else 'perturbed' if self.pushed[world] else 'idle perturbed-' if self.minus[world] else 'normal'
        result.update(final_phase_cohort=cohort,initialization_bank_index=int(self.choice[world]),
            kick_count=int(self.kick_count[world]),last_kick_tick=int(self.last_kick[world]),
            first_foot_tick=int(self.first_foot[world]),kick_delta_xy_m_s=self.last_requested[world].cpu().tolist(),kick_velocity_error_m_s=float(self.kick_error[world]))
        if self.plus[world]:result.update(perturbed_plus_row=True,perturbation='upright-cone limp pose; minimum floor height plus uniform0-60cm; independent dataset root and joint velocities',velocity_gate='first foot below1cm then40ticks',perturbed_max_ticks=150)
        if self.plus[world]:
            result['velocity_gate']=f"first foot below1cm then{self.cfg.get('plus_foot_grace',40)}ticks"
            if self.cfg.get('plus_blended'):
                result.update(perturbation='uniform whole-pose and joint-velocity blend: authored start to full perturbed+; random root velocities unchanged',initialization_blend=float(self.bank['plus_blend'][self.env._motion_ids[world],self.choice[world]]))
        if self.pushed[world]:result.update(perturbation='random locomotion limb pose/velocity with preserved target COM; independent five-body kicks at80',velocity_gate='ticks9-79 and130-150; paused80-129 for push',perturbed_max_ticks=150)
        if self.minus[world]:result.update(perturbation=f"normal idle; independent five-body kicks every{self.cfg.get('minus_kick_interval',30)}ticks",target_termination_bodies=[],sphere_only=False,stock_pose_termination=False,contact_termination=True,pushed_idle_failure_penalty=float(self.env._perturb_cfg.get('pushed_idle_failure_penalty',0.)))
        return result


class ArticulatedKicks:
    """Simultaneous horizontal COM velocity increments via J M^-1 J^T.

    Ten requested components are solved together, so impulses on one body do
    not invalidate another body's requested kick. Contacts react on next step.
    Only event ticks run this path; existing physics CUDA graph is unchanged.
    """
    def __init__(self,engine):
        self.e=engine;s=engine._solver;m=s.mj_model;self.n=engine.get_num_envs();self.dev=engine._device
        self.ids=[next(i for i in range(1,m.nbody) if m.body(i).name.endswith(name)) for name in ['right_hand','left_hand','right_foot','left_foot','pelvis']]
        self.body=[wp.array(np.full(self.n,b,np.int32),device=self.dev) for b in self.ids]
        self.jac=wp.empty((self.n,3,m.nv),dtype=float,device=self.dev)
        self.y=wp.empty((self.n,m.nv),dtype=float,device=self.dev);self.x=wp.empty_like(self.y)

    def apply(self,rows,desired):
        e=self.e;s=e._solver;d=s.mjw_data;m=s.mjw_model;state=e._sim_state.raw_state
        e._sim_state.pre_step_update();s._update_mjc_data(d,e._sim_model,state)
        mjw.kinematics(m,d);mjw.com_pos(m,d);mjw.crb(m,d);mjw.factor_m(m,d)
        xipos=wp.to_torch(d.xipos);mat=[]
        for b,body in zip(self.ids,self.body):
            point=wp.from_torch(xipos[:,b].contiguous(),dtype=wp.vec3)
            mjw.jac(m,d,self.jac,None,point,body)
            mat.append(wp.to_torch(self.jac)[:,:2].clone())
        jac=torch.cat(mat,1);inverse=[]
        for j in range(10):
            wp.to_torch(self.y).copy_(jac[:,j]);mjw.solve_m(m,d,self.x,self.y)
            inverse.append(wp.to_torch(self.x).clone())
        inv=torch.stack(inverse,-1);j=jac[rows];a=inv[rows]
        mobility=j@a;wanted=desired.flatten(1)
        impulses=torch.linalg.solve(mobility,wanted[:,:,None])
        delta=(a@impulses).squeeze(-1)
        measured=(j@delta[:,:,None]).squeeze(-1)
        error=(measured-wanted).abs().amax(-1)
        if not torch.isfinite(delta).all() or float(error.max())>.002:
            raise RuntimeError('Articulated kick solve failed')
        wp.to_torch(d.qvel)[rows]+=delta
        s._update_newton_state(e._sim_model,state,d,state);e._sim_state.post_step_update();e.refresh_body_velocities()
        return error
