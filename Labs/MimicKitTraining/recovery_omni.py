"""Opt-in get-up starts within fixed idle rows; next-tick phase feedback."""
import math
from pathlib import Path
import torch
from anim.motion_lib import MotionLib
from envs.base_env import DoneFlags
from envs.deepmimic_env import compute_done
from omni_walk import OmniWalkEnv, phase_at
from omni_policy import circular_phase
from absolute_walk import world_velocities
from flat_com import flat_com_velocity, expanded_band, band_loss
from util import torch_util as q


def rotate_frame(values, rotation):
    """One fixed world-Z rotation; joint coordinates and floor height stay intact."""
    root, rot, vel, ang, joints, dof = values
    return (q.quat_rotate(rotation, root), q.quat_mul(rotation, rot),
            q.quat_rotate(rotation, vel), q.quat_rotate(rotation, ang), joints, dof)



def build_reset_dof_cache(lib):
    """Evaluate the existing interpolation once at every admitted source frame.

    Use the same arithmetic as reset sampling (not raw source joint angles):
    even a nominal frame boundary can take the upstream small-angle blend.
    """
    counts=lib._motion_num_frames
    width=int(counts.max())
    frame=torch.arange(width,device=lib._device,dtype=torch.float32)
    ids=torch.arange(len(counts),device=lib._device)[:,None].expand(-1,width)
    frames=torch.minimum(frame[None].expand_as(ids),counts[:,None]-1)
    starts=frames*lib.get_motion_length(ids)/(counts[:,None]-1)
    joints=lib.calc_motion_frame(ids.flatten(),starts.flatten())[4]
    return lib.joint_rot_to_dof(joints).reshape(len(counts),width,-1)


def random_start_rows(indices, num_envs, fraction, fixed_motion=None):
    """Fixed, evenly distributed cohort; short episodes cannot change its share."""
    if not math.isfinite(fraction) or not 0. <= fraction <= 1.:
        raise ValueError('Recovery random start fraction must be in [0, 1]')
    mask = torch.zeros(num_envs, device=indices.device, dtype=torch.bool)
    if fixed_motion is not None:
        # Stratify within each motion so equal motion/start fractions do not
        # select the same rows (all back random, all front frame zero).
        groups = [indices[fixed_motion[indices] == motion] for motion in torch.unique(fixed_motion[indices])]
        counts = [math.floor(len(group)*fraction) for group in groups]
        remainder = round(len(indices)*fraction)-sum(counts)
        order = sorted(range(len(groups)), key=lambda i: len(groups[i])*fraction-counts[i], reverse=True)
        for i in order[:remainder]:
            counts[i] += 1
        for group, count in zip(groups, counts):
            if count:
                selected = torch.floor((torch.arange(count, device=indices.device)+.5)*len(group)/count).long()
                mask[group[selected]] = True
        return mask
    count = round(len(indices) * fraction)
    if count:
        selected = torch.floor((torch.arange(count, device=indices.device) + .5) * len(indices) / count).long()
        mask[indices[selected]] = True
    return mask

class RecoveryOmniEnv(OmniWalkEnv):
    def __init__(self, *args, **kwargs):
        self._recovery_ready = False
        super().__init__(*args, **kwargs)

    def _build_sim_tensors(self, config):
        super()._build_sim_tensors(config)
        cfg = config['idle_recovery']
        self._recovery_frame_zero = bool(cfg.get('start_at_frame_zero', False))
        self._recovery_timeout_only = bool(cfg.get('timeout_only', False))
        self._recovery_sphere_only = bool(cfg.get('sphere_only', False))
        names = [point['body'] for point in self._termination_points]
        self._recovery_target_bodies = list(cfg.get('target_termination_bodies', names))
        if not self._recovery_target_bodies or any(name not in names for name in self._recovery_target_bodies):
            raise ValueError('Unknown or empty recovery target termination bodies')
        self._recovery_target_indices = [names.index(name) for name in self._recovery_target_bodies]
        self._absolute_recovery = bool(cfg.get('absolute_target', False))
        self._reset_after_getup = bool(cfg.get('reset_at_getup_end', False))
        if self._adaptive_rows is not None:
            raise ValueError('Recovery experiment requires fixed motion assignments')
        self._recovery_lib = MotionLib(cfg['motion_file'], self._kin_char_model, self._device)
        self._recovery_reset_lib = MotionLib(cfg['reset_motion_file'], self._kin_char_model, self._device)
        torch.testing.assert_close(self._recovery_reset_lib.get_motion_lengths(),self._recovery_lib.get_motion_lengths())
        torch.testing.assert_close(self._recovery_reset_lib._motion_num_frames,self._recovery_lib._motion_num_frames)
        self._reset_dof_cache=build_reset_dof_cache(self._recovery_reset_lib)
        self._cache_recovery_spawns=True
        if self._recovery_lib.get_num_motions() != 2:
            raise ValueError('Expected front and back recovery motions')
        n = self.get_num_envs()
        count = round(self._idle_rows * float(cfg['fraction']))
        # Evenly spread recovery membership through both equipment idle groups.
        indices = torch.floor((torch.arange(count,device=self._device)+.5)*self._idle_rows/count).long()
        self._recovery_ids = indices
        self._recovery_rows = torch.zeros(n,device=self._device,dtype=torch.bool)
        self._recovery_rows[indices] = True
        self._recovery_random_start_fraction = float(cfg.get('random_start_fraction', 0. if self._recovery_frame_zero else 1.))
        self._recovery_random_start_rows = random_start_rows(indices, n, self._recovery_random_start_fraction)
        self._recovery_motion = torch.zeros(n,device=self._device,dtype=torch.long)
        self._recovery_fixed_motion = None
        if 'back_row_fraction' in cfg:
            fraction = float(cfg['back_row_fraction'])
            if not math.isfinite(fraction) or not 0 <= fraction <= 1:
                raise ValueError('Back recovery row fraction must be in [0, 1]')
            clip_names = [Path(self._recovery_lib.get_motion_file(i)).stem.lower() for i in range(2)]
            back = [i for i, name in enumerate(clip_names) if 'back' in name]
            if len(back) != 1:
                raise ValueError('Expected exactly one named back get-up clip')
            self._recovery_fixed_motion = torch.full((n,), 1-back[0], device=self._device, dtype=torch.long)
            back_mask = random_start_rows(indices, n, fraction)
            self._recovery_fixed_motion[back_mask] = back[0]
            self._recovery_assignment_report = dict(
                back_rows=int(back_mask.sum()), front_rows=count-int(back_mask.sum()),
                motion_files=clip_names, back_motion_index=back[0])
            self._recovery_random_start_rows = random_start_rows(
                indices, n, self._recovery_random_start_fraction, self._recovery_fixed_motion)
        self._recovery_start = torch.zeros(n,device=self._device)
        self._recovery_start_frame = torch.zeros(n,device=self._device,dtype=torch.long)
        self._feedback_phase = torch.zeros((n,2),device=self._device)
        self._feedback_phase[:,0] = 1.
        self._pending_phase = self._feedback_phase.clone()
        lib = self._recovery_lib
        # Match the idle assigned to each row: drawn/unarmed idle first-frame
        # headings differ slightly. Rotate the entire clip, never each tick's
        # target toward the simulated pelvis.
        motion_ids = torch.arange(self._motion_lib.get_num_motions(), device=self._device)
        idle_rot = self._motion_lib.calc_motion_frame(motion_ids, torch.zeros_like(motion_ids, dtype=torch.float32))[1]
        ends = torch.arange(2, device=self._device)
        end_rot = lib.calc_motion_frame(ends, lib.get_motion_length(ends))[1]
        self._recovery_rotation = q.quat_mul(q.calc_heading_quat(idle_rot)[:, None].expand(-1, 2, -1),
            q.calc_heading_quat_inv(end_rot)[None].expand(len(motion_ids), -1, -1))
        if not cfg.get('align_final_heading_to_idle', False):
            self._recovery_rotation.zero_(); self._recovery_rotation[..., 3] = 1.
        rotations = torch.cat((lib._frame_root_rot[:,None],lib._frame_joint_rot),1)
        dot = (rotations*rotations.roll(-1,0)).sum(-1).abs()
        self._recovery_moving = ((1-dot.square()).clamp_min(0).sqrt() >= .001) & (dot < 1)
        if self._flat_com_config:
            self._recovery_com_bands=torch.zeros((len(motion_ids),2,2,2),device=self._device)
            for idle in torch.where(self._gaits == -1)[0].tolist():
                for i in range(2):
                    times=torch.arange(math.ceil(float(lib.get_motion_length(i))*240),device=self._device)/240
                    ids=torch.full_like(times,i,dtype=torch.long)
                    root,rot,vel,ang,joints,dof=rotate_frame(lib.calc_motion_frame(ids,times),self._recovery_rotation[idle,i].expand(len(times),-1))
                    pos,rotation=self._kin_char_model.forward_kinematics(root,rot,joints)
                    v,w=self._recovery_velocities(pos,rotation,vel,ang,dof,ids,times)
                    com=v+torch.cross(w,q.quat_rotate(rotation,self._body_com[:1].expand_as(pos)),dim=-1)
                    self._recovery_com_bands[idle,i]=expanded_band(flat_com_velocity(com[:,self._flat_com_ids],self._flat_com_masses),float(self._flat_com_config['leeway']))
        if cfg.get('termination_penalty_per_tick', 0.):
            raise ValueError('Termination penalty experiment was removed; rebuild the task config')
        self._recovery_pelvis_velocity_multiplier = float(cfg.get('pelvis_linear_velocity_multiplier', 1.))
        if not math.isfinite(self._recovery_pelvis_velocity_multiplier) or self._recovery_pelvis_velocity_multiplier < 1.:
            raise ValueError('Invalid recovery pelvis velocity multiplier')
        self._recovery_target_radius_m = float(cfg.get('target_radius_m', self.target_radius_m))
        if not math.isfinite(self._recovery_target_radius_m) or self._recovery_target_radius_m <= 0:
            raise ValueError('Invalid recovery sphere radius')
        overrides = cfg.get('target_radii_m', {})
        if any(name not in names for name in overrides):
            raise ValueError('Unknown recovery sphere body')
        self._recovery_target_radii_m = {name: float(overrides.get(name, self._recovery_target_radius_m)) for name in names}
        if any(not math.isfinite(v) or v <= 0 for v in self._recovery_target_radii_m.values()):
            raise ValueError('Invalid recovery body sphere radius')
        self._recovery_target_radius_sq = torch.tensor(
            [self._recovery_target_radii_m[name] for name in self._recovery_target_bodies],
            device=self._device).square()
        if self._recovery_pelvis_velocity_multiplier != 1.:
            self.loss_term_names = (*self.loss_term_names, 'pelvis_velocity_extra')
            self.loss_weights['pelvis_velocity_extra'] = self.loss_weights['linear_velocity_mse'] * (self._recovery_pelvis_velocity_multiplier - 1.) / self._kin_char_model.get_num_joints()
            self.loss_terms = torch.zeros((n, len(self.loss_term_names)), device=self._device)
            self._completed_loss_totals = torch.zeros(len(self.loss_term_names)+1, device=self._device)
        self._recovery_ready = True

    def recovery_active(self, dt=0.):
        # Float32 30-Hz accumulation can undershoot the endpoint by a few
        # nanoseconds; do not grant an unintended extra policy tick.
        return self._recovery_rows & ((self._time_buf+self._recovery_start+dt) < self._recovery_lib.get_motion_length(self._recovery_motion)-1e-6)

    def recovery_reference_active(self):
        return self._recovery_rows if self._reset_after_getup else self.recovery_active()

    def _target_positions(self, actual, reference, env_ids=None):
        following = super()._target_positions(actual, reference, env_ids)
        if not self._recovery_ready or not self._absolute_recovery:
            return following
        active = self.recovery_reference_active()
        if env_ids is not None: active = active[env_ids]
        # At the very first idle tick this mask is false: pelvis-XY following
        # resumes immediately, with authored height and heading unchanged.
        return torch.where(active[:, None, None], reference, following)

    def queue_phase_prediction(self, prediction):
        # Called during action selection, but current observation/labels remain
        # untouched until step(). Prediction belongs to the following tick.
        ids=self._recovery_ids
        value=torch.nn.functional.normalize(prediction,dim=-1,eps=1e-6)
        self._pending_phase[ids]=value

    def step(self, action):
        ids=self._recovery_ids
        self._feedback_phase[ids]=self._pending_phase[ids]
        return super().step(action)

    def _get_motion_times(self, env_ids=None):
        times=super()._get_motion_times(env_ids)
        if not self._recovery_ready:return times
        if self._reset_after_getup:return times
        ids=self._motion_ids if env_ids is None else self._motion_ids[env_ids]
        phase=self._feedback_phase if env_ids is None else self._feedback_phase[env_ids]
        idle=self._recovery_rows & ~self.recovery_active()
        if env_ids is not None:idle=idle[env_ids]
        normalized=torch.atan2(phase[:,1],phase[:,0])/(2*math.pi)
        predicted_time=torch.remainder(normalized-self._phase_offsets[ids],1.)*self._motion_lib.get_motion_length(ids)
        return torch.where(idle,predicted_time,times)

    def _reset_ref_motion(self, env_ids):
        super()._reset_ref_motion(env_ids)
        if not self._recovery_ready:return
        ids=env_ids[self._recovery_rows[env_ids]]
        if not len(ids):return
        lib=self._recovery_lib
        motions=(self._recovery_fixed_motion[ids] if self._recovery_fixed_motion is not None
                 else torch.randint(2,(len(ids),),device=self._device))
        self._recovery_motion[ids]=motions
        # Uniform source-frame sampling. End-reset episodes exclude the final
        # frame so every start has at least one authored interval to complete.
        frames=lib._motion_num_frames[motions]-int(self._reset_after_getup)
        frame=(torch.zeros(len(ids),device=self._device) if self._recovery_random_start_fraction == 0.
               else torch.where(self._recovery_random_start_rows[ids],
                   torch.floor(torch.rand(len(ids),device=self._device)*frames), 0.))
        self._recovery_start_frame[ids]=frame.long()
        starts=frame*lib.get_motion_length(motions)/(lib._motion_num_frames[motions]-1)
        self._recovery_start[ids]=starts
        phase=circular_phase(starts/lib.get_motion_length(motions))
        self._feedback_phase[ids]=phase
        self._pending_phase[ids]=phase
        # A final-frame start has already reached idle. Initialize its reference
        # from that same feedback phase rather than the unrelated idle RNG time.
        idle_ids=ids[~self.recovery_active()[ids]]
        if len(idle_ids):
            values=self._motion_lib.calc_motion_frame(self._motion_ids[idle_ids],self._get_motion_times(idle_ids))
            for destination,value in zip((self._ref_root_pos,self._ref_root_rot,self._ref_root_vel,self._ref_root_ang_vel,self._ref_joint_rot,self._ref_dof_vel),values):
                destination[idle_ids]=value
        self._replace_recovery_reference()
        self._ref_dof_pos[ids]=self._motion_lib.joint_rot_to_dof(self._ref_joint_rot[ids])

    def _update_ref_motion(self):
        super()._update_ref_motion()
        if self._recovery_ready:self._replace_recovery_reference()

    def _ref_state_init(self,env_ids):
        super()._ref_state_init(env_ids)
        if not self._recovery_ready:return
        ids=env_ids[self.recovery_active()[env_ids]]
        if not len(ids):return
        # Only the spawned articulation uses IK. Reward/reference tensors and
        # authored velocity stay intact; FK is refreshed by the normal reset.
        if self._cache_recovery_spawns:
            dofs=self._reset_dof_cache[self._recovery_motion[ids],self._recovery_start_frame[ids]]
        else:
            values=self._recovery_reset_lib.calc_motion_frame(self._recovery_motion[ids],self._recovery_start[ids])
            dofs=self._recovery_reset_lib.joint_rot_to_dof(values[4])
        self._engine.set_dof_pos(ids,self._get_char_id(),dofs)

    def _replace_recovery_reference(self):
        ids=self._recovery_ids
        if not len(ids):return
        active=self.recovery_reference_active()[ids]
        values=self._recovery_lib.calc_motion_frame(self._recovery_motion[ids],self._time_buf[ids]+self._recovery_start[ids])
        values=rotate_frame(values,self._recovery_rotation[self._motion_ids[ids],self._recovery_motion[ids]])
        for destination,value in zip((self._ref_root_pos,self._ref_root_rot,self._ref_root_vel,self._ref_root_ang_vel,self._ref_joint_rot,self._ref_dof_vel),values):
            mask=active.reshape((-1,)+(1,)*(value.ndim-1))
            destination[ids]=torch.where(mask,value,destination[ids])
        pos,rot=self._kin_char_model.forward_kinematics(self._ref_root_pos[ids],self._ref_root_rot[ids],self._ref_joint_rot[ids])
        self._ref_body_pos[ids]=pos;self._ref_body_rot[ids]=rot

    def _recovery_velocities(self,pos,rot,velocity,angular,dof,ids,times):
        frame,_,_=self._recovery_lib._calc_frame_blend(ids,times)
        moving=self._recovery_moving[frame]
        local=(dof@self._velocity_mapping).view(pos.shape[0],-1,3)
        return world_velocities(pos,rot,velocity,angular*moving[:,:1],local*moving[:,1:,None],self._velocity_parents)

    def _world_reference_velocities(self,pos,rot,velocity,angular,dof,ids,times):
        v,w=super()._world_reference_velocities(pos,rot,velocity,angular,dof,ids,times)
        if not self._recovery_ready or not len(self._recovery_ids):return v,w
        rows=self._recovery_ids
        rv,rw=self._recovery_velocities(pos[rows],rot[rows],velocity[rows],angular[rows],dof[rows],self._recovery_motion[rows],self._time_buf[rows]+self._recovery_start[rows])
        mask=self.recovery_reference_active()[rows,None,None]
        v[rows]=torch.where(mask,rv,v[rows]);w[rows]=torch.where(mask,rw,w[rows])
        return v,w

    def _tracking_losses(self,pos,rot,vel,ang,target_vel,target_ang):
        terms=super()._tracking_losses(pos,rot,vel,ang,target_vel,target_ang)
        if self._flat_com_config and self._recovery_ready and len(self._recovery_ids):
            velocity=flat_com_velocity(self._engine.get_body_vel(self._get_char_id())[:,self._flat_com_ids],self._flat_com_masses)
            extra=band_loss(velocity,self._recovery_com_bands[self._motion_ids,self._recovery_motion])*self._flat_com_weight
            terms[:,-1]=torch.where(self.recovery_reference_active(),extra,terms[:,-1])
        if getattr(self, '_recovery_pelvis_velocity_multiplier', 1.) != 1.:
            # Add one extra copy of the pelvis contribution, preserving the
            # original all-body denominator and every other body's weight.
            extra = (vel[:, 0] - target_vel[:, 0]).square().mean(-1)
            extra = extra * self.loss_weights['pelvis_velocity_extra'] * self._recovery_rows
            terms = torch.cat((terms, extra[:, None]), -1)
        return terms

    def _command_phase(self,env_ids=None,dt=0.):
        ids,phase=super()._command_phase(env_ids,dt)
        if not self._recovery_ready:return ids,phase
        mask=self._recovery_rows if env_ids is None else self._recovery_rows[env_ids]
        feedback=self._feedback_phase if env_ids is None else self._feedback_phase[env_ids]
        return ids,torch.where(mask[:,None],feedback,phase)

    def next_phase_target(self):
        # Clock label during get-up; one nominal idle tick after the current
        # feedback phase thereafter. Never train against the output itself.
        dt=self._engine.get_timestep()
        ids=self._motion_ids
        target=phase_at(self._get_motion_times(),self._motion_lib.get_motion_length(ids),self._phase_offsets[ids],dt)
        getup=(self._time_buf+self._recovery_start+dt)/self._recovery_lib.get_motion_length(self._recovery_motion)
        recovery_label=circular_phase(getup.clamp(0,1))
        return torch.where(self.recovery_reference_active()[:,None],recovery_label,target)

    def _update_done(self):
        super()._update_done()
        if not self._recovery_ready:return
        ids=self._recovery_ids;char=self._get_char_id()
        if not len(ids):return
        if self._recovery_timeout_only or self._recovery_sphere_only:
            # Failure checks and authored clip completion are independent.
            ended=self._time_buf[ids]>=self._episode_length
            if self._reset_after_getup:
                ended=ended | ~self.recovery_active()[ids]
            self._done_buf[ids]=torch.where(ended,
                DoneFlags.TIME.value,DoneFlags.NULL.value).to(self._done_buf.dtype)
            if self._reset_after_getup:
                # Authored clip completion is a true terminal state, not a
                # time-limit truncation with a hypothetical continuation value.
                self._done_buf[ids]=torch.where(~self.recovery_active()[ids],
                    DoneFlags.SUCC.value,self._done_buf[ids]).to(self._done_buf.dtype)
            if self._recovery_sphere_only:
                failed=(self.target_distances_sq[ids][:,self._recovery_target_indices]>self._recovery_target_radius_sq).any(-1)&(self._time_buf[ids]>0)
                self._done_buf[ids]=torch.where(failed,DoneFlags.FAIL.value,self._done_buf[ids]).to(self._done_buf.dtype)
            return
        # Retain existing positional-pose and 27cm target checks, but permit
        # hands, knees, torso and head to contact the floor during recovery.
        done=compute_done(self._done_buf[ids],self._time_buf[ids],self._episode_length,
            self._engine.get_root_rot(char)[ids],self._engine.get_body_pos(char)[ids],
            self._ref_root_rot[ids],self._ref_body_pos[ids],
            torch.zeros_like(self._ref_body_pos[ids]),torch.empty(0,device=self._device,dtype=torch.long),
            self._pose_termination,self._pose_termination_dist,self._global_obs,True,
            self._get_motion_times(ids),self._motion_lib.get_motion_length(self._motion_ids[ids]),
            torch.zeros(len(ids),device=self._device,dtype=torch.bool),self._track_global_root())
        failed=(self.target_distances_sq[ids][:,self._recovery_target_indices]>self._recovery_target_radius_sq).any(-1)&(self._time_buf[ids]>0)
        done[failed]=DoneFlags.FAIL.value
        if self._reset_after_getup:
            ended=~self.recovery_active()[ids]
            done[ended & (done != DoneFlags.FAIL.value)]=DoneFlags.SUCC.value
        self._done_buf[ids]=done

    def recovery_row_metadata(self,world):
        recovery=bool(self._recovery_rows[world])
        m=int(self._recovery_motion[world])
        return dict(recovery_row=recovery,auto_phase_feedback=recovery,
            recovery_start_mode=('random source frame' if self._recovery_random_start_rows[world] else 'frame 0') if recovery else None,
            timeout_only=bool(recovery and self._recovery_timeout_only),
            sphere_only=bool(recovery and self._recovery_sphere_only),
            target_position_mode=('absolute world get-up; reset at clip end' if self._reset_after_getup else 'absolute world during get-up; pelvis XY following during idle') if recovery and self._absolute_recovery else 'pelvis XY following',
            getup_world_yaw_degrees=float(q.calc_heading(self._recovery_rotation[self._motion_ids[world],m])*180/math.pi) if recovery else None,
            reset_at_getup_end=bool(recovery and self._reset_after_getup),
            target_radius_m=self._recovery_target_radius_m if recovery else self.target_radius_m,
            target_radii_m=self._recovery_target_radii_m if recovery else {},
            pelvis_linear_velocity_multiplier=self._recovery_pelvis_velocity_multiplier if recovery else 1.,
            target_termination_bodies=([] if self._recovery_timeout_only else self._recovery_target_bodies) if recovery else [point['body'] for point in self._termination_points],
            recovery_motion_file=self._recovery_lib.get_motion_file(m) if recovery else None,
            recovery_start_seconds=float(self._recovery_start[world]) if recovery else None,
            phase_target_mode=('get-up authored clock; reset at clip end' if self._reset_after_getup else 'get-up authored clock, then idle at prior-tick predicted phase') if recovery else 'clock')

    def replay_loss_metadata(self):
        result=super().replay_loss_metadata()
        result['recovery_target_termination_bodies']=[] if self._recovery_timeout_only else self._recovery_target_bodies
        result['recovery_timeout_only']=self._recovery_timeout_only
        if self._absolute_recovery:
            result['objective'] += '; recovery override: absolute world get-up targets, then pelvis-XY-relative idle'
        result['recovery_heading']='Fixed clip yaw aligns final get-up pelvis with assigned idle first-frame pelvis heading'
        if self._reset_after_getup:
            result['objective'] += '; recovery rows end at final authored get-up frame and reset, no idle tail'
        result['recovery_pelvis_linear_velocity_multiplier'] = self._recovery_pelvis_velocity_multiplier
        result['recovery_target_radius_m'] = self._recovery_target_radius_m
        result['terminal_meaning'] = '1=failure; 2=authored motion completed (zero continuation value); 3=time-limit truncation'
        result['pelvis_velocity_extra_definition'] = 'Extra pelvis linear-velocity MSE contribution on recovery rows only; original all-body denominator retained; angular velocity unchanged'
        return result
