"""Differentiable copy of the frozen locomotion task's scoring, experiments only.

Physical observations omit pelvis XY. Three actual pelvis positions therefore
accompany the observation history; otherwise the AE's translation cannot be
recovered exactly. Validate every term against the frozen environment before use.
"""
import math
import torch
from supermimic_structured import SkeletonProjection, matrix_from_quat, matrix_from_six


def com2_failure_surrogate(velocity,target,min_ratio=.7,temperature=.05):
    """Smooth derivative for existing speed/direction boundaries, experiments only.

    The simulator's hard done flag and terminal reward remain authoritative.
    Return both the hard predicate and its smooth approximation for validation.
    """
    speed=velocity.norm(dim=-1);reference=target.norm(dim=-1).clamp_min(1e-6)
    ratio=speed/reference
    cosine=(velocity*target).sum(-1)/(speed*reference).clamp_min(1e-6)
    margins=torch.stack((min_ratio-ratio,ratio-1.7,math.cos(math.pi/4)-cosine),-1)
    worst=margins.amax(-1)
    return worst>0,torch.sigmoid(worst/temperature)


def safe_reference_slerp(q0,q1,t):
    """Preserve the frozen library's constant branches without masked 0/0 grads."""
    dot=(q0*q1).sum(-1,keepdim=True)
    q1=torch.where(dot<0,-q1,q1);dot=dot.abs()
    active=(dot<1)&((1-dot.square())>=1e-6)
    safe=torch.where(active,dot,torch.zeros_like(dot))
    angle=safe.acos();sine=(1-safe.square()).sqrt();t=t[...,None]
    result=((1-t)*angle).sin()/sine*q0+(t*angle).sin()/sine*q1
    result=torch.where(active,result,(q0+q1)*.5)
    return torch.where(dot>=1,q0,result)


def forward_kinematics(skeleton, root_pos, root_matrix, joint_matrices):
    positions=[root_pos];rotations=[root_matrix]
    for j in range(1,len(skeleton.parents)):
        parent=skeleton.parents[j]
        positions.append(positions[parent]+(rotations[parent]@skeleton.translations[j,:,None]).squeeze(-1))
        rotations.append(rotations[parent]@skeleton.local_matrices[j]@joint_matrices[:,j-1])
    return torch.stack(positions,1),torch.stack(rotations,1)


def world_velocities(pos,rot,root_vel,root_ang,joint_local_ang,parents):
    v=[root_vel];w=[root_ang]
    relative=(rot[:,1:]@joint_local_ang[...,None]).squeeze(-1)
    for j in range(1,len(parents)):
        p=parents[j]
        v.append(v[p]+torch.cross(w[p],pos[:,j]-pos[:,p],dim=-1))
        w.append(w[p]+relative[:,j-1])
    return torch.stack(v,1),torch.stack(w,1)


class ExactReward:
    def __init__(self,ctx):
        self.ctx=ctx;self.e=ctx.e;e=self.e
        assert not bool(e._recovery_rows.any()), 'Locomotion/ordinary idle only'
        assert e._reward_form=='reciprocal_sum'
        self.skeleton=SkeletonProjection(e._kin_char_model,e._key_body_ids).to(ctx.device)

    def bodies(self,x,xy):
        e=self.e;raw=x*self.ctx.std[:146]+self.ctx.mean[:146]
        root=torch.cat((xy,raw[:,:1]),-1)
        root_r=matrix_from_six(raw[:,1:7]);joints=matrix_from_six(self.skeleton.rotations(raw))
        pos,rot=forward_kinematics(self.skeleton,root,root_r,joints)
        com=(rot@e._body_com[:1,...,None]).squeeze(-1)
        # Observation root velocity is pelvis COM velocity, not origin velocity.
        root_v=raw[:,7:10]-torch.cross(raw[:,10:13],com[:,0],dim=-1)
        local=(raw[:,97:131]@e._velocity_mapping).reshape(len(x),-1,3)
        vel,ang=world_velocities(pos,rot,root_v,raw[:,10:13],local,self.skeleton.parents)
        return pos,rot,vel,ang

    def com2(self,x,xy):
        e=self.e;_,rot,vel,ang=self.bodies(x,xy)
        offset=(rot@e._body_com[:1,...,None]).squeeze(-1)
        com_velocity=vel+torch.cross(ang,offset,dim=-1)
        return (com_velocity[:,e._com2_ids,:2]*e._com2_masses[:,None]).sum(1)

    def failure(self,x,xy,motion,age,pert):
        e=self.e
        hard,soft=com2_failure_surrogate(self.com2(x,xy),e._com2_targets[motion],e._perturb_cfg['min_speed_ratio'])
        enabled=pert&(e._gaits[motion]!=-1)&(age>e._perturb_cfg['grace_ticks'])
        return hard&enabled,soft*enabled

    def reference(self,motion,phase,times,pert):
        e=self.e
        fraction=torch.atan2(phase[:,1],phase[:,0])/(2*math.pi)
        predicted=torch.remainder(fraction-e._phase_offsets[motion],1.)*e._motion_lib.get_motion_length(motion)
        times=torch.where(pert,predicted,times)
        # The library's q0==q1 branch returns finite poses but has a masked 0/0
        # derivative with respect to phase. Use its identical forward branches
        # with safe denominators; production interpolation remains unchanged.
        lib=e._motion_lib;f0,f1,blend=lib._calc_frame_blend(motion,times)
        root=lib._frame_root_pos[f0]*(1-blend[:,None])+lib._frame_root_pos[f1]*blend[:,None]
        root=root+lib._calc_loop_offset(motion,times)
        quat=safe_reference_slerp(lib._frame_root_rot[f0],lib._frame_root_rot[f1],blend)
        joint=safe_reference_slerp(lib._frame_joint_rot[f0],lib._frame_joint_rot[f1],blend[:,None])
        vel=lib._frame_root_vel[f0];ang=lib._frame_root_ang_vel[f0];dof=lib._frame_dof_vel[f0]
        pos,rot=forward_kinematics(self.skeleton,root,matrix_from_quat(quat),matrix_from_quat(joint))
        frame,_,_=e._motion_lib._calc_frame_blend(motion,times)
        moving=e._rotation_moving[frame]
        local=(dof@e._velocity_mapping).reshape(len(dof),-1,3)*moving[:,1:,None]
        v,w=world_velocities(pos,rot,vel,ang*moving[:,:1],local,self.skeleton.parents)
        return pos,rot,v,w

    def __call__(self,history,xy_history,motion,phase,age,times,pert):
        e=self.e;n=len(history)
        positions,rotations,velocities,angular=self.bodies(history.reshape(-1,146),xy_history.reshape(-1,2))
        positions=positions.reshape(n,3,15,3);rotations=rotations.reshape(n,3,15,3,3)
        pos=positions[:,-1];rot=rotations[:,-1]
        vel=velocities.reshape(n,3,15,3)[:,-1];ang=angular.reshape(n,3,15,3)[:,-1]
        tp,tr,tv,ta=self.reference(motion,phase,times,pert)
        # Preserve the existing world-Z target and pelvis-XY following.
        shift=(pos[:,:1]-tp[:,:1])*pos.new_tensor([1.,1.,0.])
        delta=pos-(tp+shift)
        position=delta.square().mean((1,2))
        idle=e._gaits[motion]==-1
        if e._position_leeway:
            from absolute_walk import position_leeway_mse,spherical_position_mse
            allowed=position_leeway_mse(delta,e._position_legs,e._position_flat,e._position_vertical,e._position_upper)
            if e._position_leeway_scope=='idle':
                loco=spherical_position_mse(delta,e._position_locomotion) if e._position_locomotion>0 else position
                position=torch.where(idle,allowed,loco)
            else:position=allowed
        linear=(vel-tv).square().mean((1,2))
        linear=linear+(float(e._perturb_cfg.get('all_rows_pelvis_velocity_mse_multiplier',1.))-1.)*(vel[:,0]-tv[:,0]).square().mean(-1)/15
        rotation=(rot-tr).square().mean((1,2,3))
        angular_loss=(ang-ta).square().mean((1,2))
        mix=torch.ones_like(age) if e._mse_only else ((age-e._perturb_cfg['ae_ticks'])/e._perturb_cfg['blend_ticks']).clamp(0,1)
        mix=torch.where(pert,mix,torch.ones_like(mix))
        mse_mix=mix+float(e._perturb_cfg.get('ae_mse_weight',0.))*(1-mix)
        idle_scale=torch.where(pert&idle,float(e._perturb_cfg.get('idle_pose_mse_multiplier',1.)),1.)
        terms=dict(position_mse=position*e._loss_weights[0]*mse_mix*idle_scale,
                   linear_velocity_mse=linear*e._loss_weights[1]*mse_mix,
                   rotation_mse=rotation*e._loss_weights[2]*mse_mix*idle_scale,
                   angular_velocity_mse=angular_loss*e._loss_weights[3]*mse_mix)
        com=(rot@e._body_com[:1,...,None]).squeeze(-1)
        com_vel=vel+torch.cross(ang,com,dim=-1)
        if e._flat_com_config:
            from flat_com import flat_com_velocity,band_loss
            velocity=flat_com_velocity(com_vel[:,e._flat_com_ids],e._flat_com_masses)
            terms['flat_com_velocity']=band_loss(velocity,e._flat_com_bands[motion])*e._flat_com_weight*(~pert)
        if 'pelvis_velocity_extra' in e.loss_term_names:
            terms['pelvis_velocity_extra']=torch.zeros_like(age)
        raw_prior=torch.zeros_like(age)
        # Three actual poses are available starting with the second tick.
        eligible=pert&(age>=2)&(mix<1)
        if e._prior is not None and bool(eligible.any()):
            raw_prior=raw_prior.index_copy(0,eligible.nonzero().flatten(),e._prior.scorer(
                e._prior.encode(positions[eligible],rotations[eligible],ground_height=0.)))
        terms['motion_prior']=raw_prior*e._ae_weight*(1-mix)
        if 'getup_head_height' in e.loss_term_names:terms['getup_head_height']=torch.zeros_like(age)
        weight=float(e._perturb_cfg.get('extremity_speed_loss_weight',0.))
        if weight:
            ids=e._extremity_speed_ids[1:]
            relative=vel[:,ids]-vel[:,:1]-torch.cross(ang[:,:1].expand(-1,4,-1),pos[:,ids]-pos[:,:1],dim=-1)
            excess=(relative.norm(dim=-1)-e._extremity_speed_limits[motion]).clamp_min(0.)
            terms['extremity_speed_excess']=excess.square().mean(-1)*weight*pert
        if set(terms)!=set(e.loss_term_names):raise ValueError('Reward term schema mismatch: '+str((list(terms),e.loss_term_names)))
        ordered=torch.stack([terms[name] for name in e.loss_term_names],-1)
        return (1+ordered.sum(-1)).reciprocal(),ordered
