"""Continuous world-body pose MSE, fixed world heading and XY translation invariance."""
import math
import time
from pathlib import Path
import torch
from envs.char_env import CharEnv, compute_char_obs
from envs.base_env import DoneFlags
from util import torch_util
from replay import geometry


@torch.jit.script
def world_pose_mse(body_pos, body_rot, target_pos, target_rot, worst_body: bool = False):
    offset=body_pos[:,0,:].clone()
    offset[:,2]=0
    position=(body_pos-offset[:,None,:]-target_pos).square().mean(dim=-1)
    # Matrix entries avoid quaternion sign ambiguity and angle wrapping.
    axes=torch_util.quat_to_matrix(body_rot)
    target_axes=torch_util.quat_to_matrix(target_rot)
    orientation=(axes-target_axes).square().mean(dim=(-2,-1))
    if worst_body:
        # Both reported components belong to the SAME worst body. Taking each
        # component's maximum independently would define a different objective.
        index=(position+orientation).argmax(dim=-1,keepdim=True)
        position=position.gather(-1,index).squeeze(-1)
        orientation=orientation.gather(-1,index).squeeze(-1)
    else:
        position=position.mean(dim=-1)
        orientation=orientation.mean(dim=-1)
    return torch.stack((position,orientation),dim=-1)


@torch.jit.script
def height_band_mse(height, target_height):
    below=(0.80*target_height-height).clamp_min(0.)
    above=(height-1.10*target_height).clamp_min(0.)
    return (below+above).square()


@torch.jit.script
def lateral_foot_separation(left_pos, right_pos, pelvis_rot):
    # Humanoid local Y is lateral. Use the actual pelvis frame, including tilt.
    axis=torch.zeros_like(left_pos)
    axis[...,1]=1.
    lateral=torch_util.quat_rotate(pelvis_rot,axis)
    return ((left_pos-right_pos)*lateral).sum(-1).abs()


@torch.jit.script
def feet_lateral_mse(left_pos, right_pos, pelvis_rot, max_width: float):
    return (lateral_foot_separation(left_pos,right_pos,pelvis_rot)-max_width).clamp_min(0.).square()


class WorldPoseEnv(CharEnv):
    task_name='world_pose_mse'
    loss_term_names=('position_mse','orientation_mse')

    def _build_sim_tensors(self,config):
        super()._build_sim_tensors(config)
        self.worst_body=config.get('worst_body',False)
        self.height_bands_only=config.get('height_bands_only',False)
        pose=torch.tensor(config['target_pose'],device=self._device,dtype=torch.float32)[None]
        self._target_positions,self._target_rotations=self._kin_char_model.forward_kinematics(
            pose[:,:3],torch_util.exp_map_to_quat(pose[:,3:6]),self._kin_char_model.dof_to_rot(pose[:,6:]))
        self._target_positions[:,:,:2]-=pose[:,:2][:,None,:]
        self._episode_steps=round(self._episode_length/self._engine.get_timestep())
        self.height_band_weights=config.get('height_band_weights')
        assert not self.height_bands_only or self.height_band_weights is not None
        if self.height_band_weights is not None:
            assert len(self.height_band_weights)==2 and all(math.isfinite(v) and v>0 for v in self.height_band_weights)
            self.loss_term_names=(('head_height_band','pelvis_height_band') if self.height_bands_only
                else ('body_pose_mse','head_height_band','pelvis_height_band'))
            body_names=self._engine.get_obj_body_names(self._get_char_id())
            self._height_body_ids=torch.tensor([body_names.index(name) for name in ('head','pelvis')],device=self._device)
            self._height_weights=torch.tensor(self.height_band_weights,device=self._device)
        weights=(self.height_band_weights if self.height_bands_only else [1.,*self.height_band_weights]) if self.height_band_weights is not None else [1.,1.]
        self._height_slice=slice(len(weights)-2,len(weights))
        self.feet_lateral=config.get('feet_lateral_calibration')
        self.feet_lateral_termination=config.get('feet_lateral_termination',False)
        self.feet_distance_multiple=config.get('feet_distance_multiple')
        assert self.feet_distance_multiple is None or (self.feet_lateral_termination and math.isfinite(self.feet_distance_multiple) and self.feet_distance_multiple>0)
        self.termination_remaining_cost=config.get('termination_remaining_cost',False)
        assert not self.termination_remaining_cost or self.feet_lateral_termination
        assert not self.feet_lateral_termination or self.feet_lateral is not None
        self._feet_failed=torch.zeros(self.get_num_envs(),device=self._device,dtype=torch.bool)
        self.floor_impact_limit_n=config.get('floor_impact_limit_n')
        self._impact_failed=torch.zeros_like(self._feet_failed)
        self.failure_reason=torch.zeros(self.get_num_envs(),device=self._device,dtype=torch.int32)
        self.floor_peak_n=torch.zeros(self.get_num_envs(),device=self._device)
        self.floor_peak_body=torch.full((self.get_num_envs(),),-1,device=self._device,dtype=torch.long)
        if self.floor_impact_limit_n is not None:
            assert self.termination_remaining_cost and math.isfinite(self.floor_impact_limit_n) and self.floor_impact_limit_n>0
            assert self._engine._track_ground_contact_peaks
            body_names=self._engine.get_obj_body_names(self._get_char_id())
            self.floor_impact_bodies=config.get('floor_impact_bodies',[n for n in body_names if n not in ('left_foot','right_foot')])
            assert self.floor_impact_bodies and len(set(self.floor_impact_bodies))==len(self.floor_impact_bodies)
            self._impact_body_ids=torch.tensor([body_names.index(n) for n in self.floor_impact_bodies],device=self._device)
        if self.feet_lateral is not None:
            assert self.height_band_weights is not None and not self.height_bands_only
            body_names=self._engine.get_obj_body_names(self._get_char_id())
            self._left_foot_id=body_names.index('left_foot')
            self._right_foot_id=body_names.index('right_foot')
            self._pelvis_id=body_names.index('pelvis')
            self._feet_max_width=float(self.feet_lateral['max_width_m'])
            if self.feet_distance_multiple is not None:
                self._feet_reference_distance=float(torch.linalg.vector_norm(
                    self._target_positions[0,self._left_foot_id]-self._target_positions[0,self._right_foot_id]))
                self._feet_max_width=self._feet_reference_distance*self.feet_distance_multiple
            self._feet_weight=float(self.feet_lateral['weight'])
            assert math.isfinite(self._feet_max_width) and self._feet_max_width>0
            assert math.isfinite(self._feet_weight) and self._feet_weight>0
            if not self.feet_lateral_termination:
                self.loss_term_names=(*self.loss_term_names,'feet_lateral')
                weights=[*weights,self._feet_weight]
        if self.termination_remaining_cost:
            self.loss_term_names=(*self.loss_term_names,'termination_remaining')
            weights=[*weights,1.]
        self.loss_weights=dict(zip(self.loss_term_names,weights))
        self.loss_terms=torch.zeros((self.get_num_envs(),len(self.loss_term_names)),device=self._device)
        self._episode_losses=torch.zeros_like(self.loss_terms)
        self._completed_loss_totals=torch.zeros(len(self.loss_term_names)+1,device=self._device)
        self._reset_rng = torch.Generator(device=self._device).manual_seed(config['reset_seed'])
        self._pose_noise = math.radians(config['reset_joint_noise_degrees'])
        self._floor_clearance = config['reset_floor_clearance_m']
        lo, hi = self._engine.get_obj_dof_limits(0, self._get_char_id())
        self._reset_low = torch.as_tensor(lo, device=self._device, dtype=torch.float32)
        self._reset_high = torch.as_tensor(hi, device=self._device, dtype=torch.float32)
        self._starts_on_back = torch.zeros(self.get_num_envs(), device=self._device, dtype=torch.bool)
        g = geometry(Path(config['char_file']))
        shapes = g['shapes']
        tensor = lambda x: torch.tensor(x, device=self._device, dtype=torch.float32)
        self._shape_bodies = torch.tensor([g['names'].index(s['bone']) for s in shapes], device=self._device)
        self._shape_centers = tensor([s['position'] for s in shapes])
        self._shape_axes = tensor([s['axes'] for s in shapes])
        self._shape_radii = tensor([s.get('radius', 0.) for s in shapes])
        self._shape_extents = tensor([s['dimensions'] if s['kind']=='box' else [0.,0.,s.get('length',0.)] for s in shapes]) * .5
        self.valid_reset_pose_pool=config.get('valid_reset_pose_pool',False)
        if self.valid_reset_pose_pool:
            assert self.feet_lateral_termination
            self._build_valid_reset_pose_pool(config['reset_seed'])

    def _build_valid_reset_pose_pool(self,seed):
        """One startup FK/filter pass; resets only sample already-grounded poses."""
        started=time.perf_counter();count=8192
        rng=torch.Generator(device=self._device).manual_seed(seed+1)
        noise=(2*torch.rand((count,self._init_dof_pos.numel()),device=self._device,generator=rng)-1)*self._pose_noise
        dofs=(self._init_dof_pos+noise).clamp(self._reset_low,self._reset_high)
        rotations=torch.zeros((2,3),device=self._device)
        rotations[:,1]=torch.tensor([math.pi/2,-math.pi/2],device=self._device)
        rotations=torch_util.exp_map_to_quat(rotations)
        roots=[];widths=[]
        for side in range(2):
            root=self._init_root_pos.expand(count,-1).clone()
            pos,rot=self._kin_char_model.forward_kinematics(root,rotations[side].expand(count,-1),
                self._kin_char_model.dof_to_rot(dofs))
            width=self._foot_separation(pos,rot)
            root[:,2]+=self._floor_clearance-self._lowest_geometry(pos,rot)
            roots.append(root);widths.append(width)
        widths=torch.stack(widths)
        valid=torch.isfinite(widths).all(0)&(widths<=self._feet_max_width).all(0)
        self._pool_dofs=dofs[valid]
        self._pool_roots=torch.stack(roots)[:,valid]
        self._pool_rotations=rotations
        size=self._pool_dofs.shape[0]
        assert size>0,'No valid starting poses under the foot width limit'
        self.reset_pose_pool_report=dict(candidates=count,accepted=size,rejected=count-size,seed=seed+1,
            max_width_m=float(widths[:,valid].max()),limit_m=self._feet_max_width,
            front_back_probability=.5,selection='uniform with replacement; side sampled independently',
            startup_seconds=time.perf_counter()-started)

    def _lowest_geometry(self, body_pos, body_rot):
        q = body_rot[:, self._shape_bodies]
        centers = body_pos[:, self._shape_bodies] + torch_util.quat_rotate(q, self._shape_centers.expand(q.shape[0],-1,-1))
        axes = torch_util.quat_rotate(q[:,:,None,:].expand(-1,-1,3,-1), self._shape_axes.expand(q.shape[0],-1,-1,-1))
        extent = (axes[:,:,:,2].abs() * self._shape_extents).sum(-1) + self._shape_radii
        return (centers[:,:,2] - extent).amin(-1)

    def _foot_separation(self,body_pos,body_rot):
        left=body_pos[:,self._left_foot_id];right=body_pos[:,self._right_foot_id]
        if self.feet_distance_multiple is not None:
            return torch.linalg.vector_norm(left-right,dim=-1)
        return lateral_foot_separation(left,right,body_rot[:,self._pelvis_id])

    def _reset_char(self, env_ids):
        super()._reset_char(env_ids)
        n = env_ids.numel()
        if not n: return
        char = self._get_char_id()
        # Independent 50% probability; reset RNG is separate from action sampling.
        back = torch.rand(n, device=self._device, generator=self._reset_rng) < .5
        self._starts_on_back[env_ids] = back
        if self.valid_reset_pose_pool:
            indices=torch.randint(self._pool_dofs.shape[0],(n,),device=self._device,generator=self._reset_rng)
            side=back.long()
            self._engine.set_root_pos(env_ids,char,self._pool_roots[side,indices])
            self._engine.set_root_rot(env_ids,char,self._pool_rotations[side])
            self._engine.set_dof_pos(env_ids,char,self._pool_dofs[indices])
            return
        rotation = torch.zeros(n,3,device=self._device)
        rotation[:,1] = torch.where(back,-math.pi/2,math.pi/2)
        rotation = torch_util.exp_map_to_quat(rotation)
        noise = (2*torch.rand((n,self._init_dof_pos.numel()),device=self._device,generator=self._reset_rng)-1)*self._pose_noise
        dofs = (self._init_dof_pos + noise).clamp(self._reset_low,self._reset_high)
        root = self._init_root_pos.expand(n,-1).clone()
        pos,rot = self._kin_char_model.forward_kinematics(root,rotation,self._kin_char_model.dof_to_rot(dofs))
        root[:,2] += self._floor_clearance - self._lowest_geometry(pos,rot)
        self._engine.set_root_pos(env_ids,char,root)
        self._engine.set_root_rot(env_ids,char,rotation)
        self._engine.set_dof_pos(env_ids,char,dofs)

    def _compute_obs(self,env_ids=None):
        char=self._get_char_id();ids=slice(None) if env_ids is None else env_ids
        body_pos=self._engine.get_body_pos(char)[ids]
        body_rot=self._engine.get_body_rot(char)[ids]
        # Same 140 slots, but all orientation slots are world-based. Heading is
        # observable rather than penalized while hidden from the actor.
        return compute_char_obs(root_pos=self._engine.get_root_pos(char)[ids],
            root_rot=self._engine.get_root_rot(char)[ids],
            root_vel=self._engine.get_root_vel(char)[ids],
            root_ang_vel=self._engine.get_root_ang_vel(char)[ids],
            joint_rot=body_rot[:,1:],dof_vel=self._engine.get_dof_vel(char)[ids],
            key_pos=body_pos[:,self._key_body_ids],global_obs=True,root_height_obs=True)

    def _reset_envs(self,env_ids):
        super()._reset_envs(env_ids)
        self.loss_terms[env_ids]=0
        self._episode_losses[env_ids]=0
        self._feet_failed[env_ids]=False
        self._impact_failed[env_ids]=False
        self.failure_reason[env_ids]=0
        self.floor_peak_n[env_ids]=0
        self.floor_peak_body[env_ids]=-1

    def _update_reward(self):
        char=self._get_char_id()
        body_pos=self._engine.get_body_pos(char)
        if not self.height_bands_only:
            pose_terms=world_pose_mse(body_pos,self._engine.get_body_rot(char),
                self._target_positions,self._target_rotations,self.worst_body)/self._episode_steps
            if self.height_band_weights is None:
                self.loss_terms[:]=pose_terms
            else:
                self.loss_terms[:,0]=pose_terms.sum(-1)
        if self.height_band_weights is not None:
            self.loss_terms[:,self._height_slice]=height_band_mse(body_pos[:,self._height_body_ids,2],
                self._target_positions[:,self._height_body_ids,2])*self._height_weights/self._episode_steps
        if self.feet_lateral is not None:
            if self.feet_lateral_termination:
                self._feet_failed[:]=self._foot_separation(body_pos,self._engine.get_body_rot(char))>self._feet_max_width
            else:
                pelvis_rot=self._engine.get_body_rot(char)[:,self._pelvis_id]
                self.loss_terms[:,-1]=feet_lateral_mse(body_pos[:,self._left_foot_id],body_pos[:,self._right_foot_id],
                    pelvis_rot,self._feet_max_width)*self._feet_weight/self._episode_steps
        if self.floor_impact_limit_n is not None:
            peaks=self._engine.get_ground_contact_peak_forces(char)[:,self._impact_body_ids]
            self.floor_peak_n[:],index=peaks.max(-1)
            self.floor_peak_body[:]=torch.where(self.floor_peak_n>0,self._impact_body_ids[index],-1)
            self._impact_failed[:]=self.floor_peak_n>self.floor_impact_limit_n
        failed=self._feet_failed|self._impact_failed
        self.failure_reason[:]=self._feet_failed.to(torch.int32)+2*self._impact_failed.to(torch.int32)
        if self.termination_remaining_cost:
            # Current tick is already charged. Freeze its weighted pose cost for
            # each unplayed tick; timeout has no remaining ticks to charge.
            remaining=(self._episode_steps-self._timestep_buf).clamp_min(0)
            self.loss_terms[:,-1]=torch.where(failed,
                self.loss_terms[:,:-1].sum(-1)*remaining,0.)
        self._reward_buf[:]=-self.loss_terms.sum(dim=-1)
        self._episode_losses.add_(self.loss_terms)
        ended=(self._timestep_buf==self._episode_steps)|failed
        self._completed_loss_totals[:-1].add_(torch.where(ended[:,None],self._episode_losses,0.).sum(0))
        self._completed_loss_totals[-1].add_(ended.sum())

    def _update_done(self):
        super()._update_done()
        if self.feet_lateral_termination:
            self._done_buf[:]=torch.where(self._feet_failed|self._impact_failed,DoneFlags.FAIL.value,self._done_buf)

    def take_completed_losses(self):
        sums=self._completed_loss_totals.cpu().tolist()
        self._completed_loss_totals.zero_()
        if not sums[-1]:return None
        terms=[v/sums[-1] for v in sums[:-1]]
        return dict(zip((*self.loss_term_names,'total'),[*terms,sum(terms)]))
