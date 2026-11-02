"""Ten-motion policy with backward-compatible signed limp commands."""
import torch
import warp as wp
from omni_walk import OmniWalkEnv, centre_distances
from absolute_walk import AbsoluteWalkEnv
from envs.base_env import DoneFlags
from util import torch_util
from head_strength import torque_multipliers, strength_fraction


@torch.jit.script
def static_yaw_alignment(actual_rot: torch.Tensor, reference_rot: torch.Tensor):
    """Best world-Z-only pelvis alignment; retain pitch/roll and joint error."""
    a = torch_util.quat_to_matrix(actual_rot)
    r = torch_util.quat_to_matrix(reference_rot)
    cosine = (a[:, 0] * r[:, 0] + a[:, 1] * r[:, 1]).sum(-1)
    sine = (a[:, 1] * r[:, 0] - a[:, 0] * r[:, 1]).sum(-1)
    # At a relative 180-degree tilt the best yaw is ambiguous. Use the most
    # jointly horizontal corresponding axis, preserving yaw equivariance.
    score = (a[:, :2].square().sum(1) * r[:, :2].square().sum(1))
    axis = score.argmax(-1, keepdim=True)
    ax = a[:, 0].gather(1, axis).squeeze(1)
    ay = a[:, 1].gather(1, axis).squeeze(1)
    rx = r[:, 0].gather(1, axis).squeeze(1)
    ry = r[:, 1].gather(1, axis).squeeze(1)
    singular = cosine.square() + sine.square() < 1e-10
    angle = torch.atan2(torch.where(singular, ay*rx-ax*ry, sine),
                        torch.where(singular, ax*rx+ay*ry, cosine))
    z = torch.zeros_like(angle)
    return torch.stack((z, z, torch.sin(angle*.5), torch.cos(angle*.5)), -1)


class PeriodicPelvisTarget:
    """Fixed world-space sphere, re-anchored horizontally every 70 ticks."""
    def __init__(self, windows, device):
        self.windows = windows.long()
        self.age = torch.zeros_like(self.windows)
        self.actual_anchor = torch.zeros((len(windows), 3), device=device)
        self.reference_anchor = torch.zeros_like(self.actual_anchor)
        self.target = torch.zeros_like(self.actual_anchor)
        self.radius = torch.full((len(windows),), .40, device=device)
        self.ready = torch.ones_like(self.windows, dtype=torch.bool)

    def reset(self, ids, actual, reference):
        self.age[ids] = 0
        self.actual_anchor[ids] = actual
        self.reference_anchor[ids] = reference
        self.target[ids] = actual
        self.target[ids, 2] = reference[:, 2]

    def sphere_failed(self, actual):
        return (actual - self.target).square().sum(-1) > (self.radius + 1e-5).square()

    def update(self, actual, reference):
        self.age.add_(1)
        recenter = (self.age % self.windows) == 0
        self.actual_anchor.copy_(torch.where(recenter[:, None], actual, self.actual_anchor))
        self.reference_anchor.copy_(torch.where(recenter[:, None], reference, self.reference_anchor))
        self.target.copy_(self.actual_anchor + reference - self.reference_anchor)
        # Recentring forgives old horizontal drift, never the reference height.
        self.target[:, 2] = reference[:, 2]


class SlowLocoEnv(OmniWalkEnv):
    task_name = 'uefn_slow_loco_mse'

    def _build_sim_tensors(self, config):
        super()._build_sim_tensors(config)
        rows = self._omni_manifest['motions']
        names = [r['id'] for r in rows]
        assert names == ['crawl', 'crawl_idle', 'agonising', 'agonising_idle', 'limpL', 'limpR', 'lying', 'sitting', 'limpL_idle', 'limpR_idle']
        self.failure_penalty = float(config.get('slow_loco_failure_penalty', 0.))
        assert self.failure_penalty in (0., 100.)
        assert config.get('slow_loco_signed_limp_idles') is True
        self.motion_labels = names
        self.command_slots = names[:8]
        self._stationary_limp_idle = torch.tensor([n in ('limpL_idle','limpR_idle') for n in names], device=self._device)
        self._static_motion = torch.tensor([n in ('crawl_idle', 'agonising', 'agonising_idle', 'lying', 'sitting', 'limpL_idle', 'limpR_idle')
            for n in names], device=self._device)
        # Parent aliases reference rotations. Detach before aligning reward targets.
        self.reward_target_rot = self._ref_body_rot.clone()
        subset = config.get('slow_loco_motion_subset')
        self._motion_subset = subset
        self.active_motion_labels = list(subset) if subset else names
        if subset:
            assert len(subset) == len(set(subset)) and all(n in names for n in subset)
            assert self._adaptive_rows is None, 'Subset sampling requires fixed rows'
            active = torch.tensor([names.index(n) for n in subset], device=self._device)
            self._fixed_motion_ids = active[torch.arange(self.get_num_envs(), device=self._device) % len(active)]
            # This temporary subset contains only locomotion; no idle row prefix.
            assert all(int(self._gaits[names.index(n)]) != -1 for n in subset)
            self._idle_rows = 0
        if config.get('slow_loco_disabled_curriculum'):
            from disabled_limb_rules import cohorts
            self._prepared_cohort = torch.tensor(cohorts(self._fixed_motion_ids.cpu().numpy()), device=self._device)
            eligible = torch.tensor([0,1,2,3,4,5,8,9], device=self._device)
            for cohort in (1,2,3):
                worlds = (self._prepared_cohort == cohort).nonzero().flatten()
                allowed = eligible[eligible != 0] if cohort == 3 else eligible
                self._fixed_motion_ids[worlds] = allowed[torch.arange(len(worlds),device=self._device) % len(allowed)]
        self._crawl_only_experiment = bool(config.get('slow_loco_crawl_only_experiment', False))
        if self._crawl_only_experiment:
            assert config.get('slow_loco_disabled_curriculum') and subset is None
            self._fixed_motion_ids.fill_(0)
            self._prepared_cohort.fill_(2)
            self._idle_rows = 0
            self.active_motion_labels = ['crawl']
        self._failure_penalty_by_row = torch.full((self.get_num_envs(),), self.failure_penalty, device=self._device)
        if hasattr(self, '_prepared_cohort'):
            self._failure_penalty_by_row.mul_(torch.where(self._prepared_cohort > 0, 5., 1.))
        self.motion_sampling = dict(active_motions=self.active_motion_labels,
            counts={n: int((self._fixed_motion_ids == i).sum()) for i,n in enumerate(names)},
            preserved_motion_onehot_order=self.command_slots)
        self._motion_onehot = torch.zeros((10,8), device=self._device)
        self._motion_onehot[:8] = torch.eye(8, device=self._device)
        self._motion_onehot[8,4] = -1.
        self._motion_onehot[9,5] = -1.
        self._motion_limbs = torch.ones((10, 4), device=self._device)
        self._motion_limbs[[4,8], 3] = 0
        self._motion_limbs[[5,9], 2] = 0
        self._limb_enabled = self._motion_limbs[self._fixed_motion_ids].clone()
        mask = wp.to_torch(self._engine.transfer_contact.p.motor_enabled)
        mask.fill_(1.)
        body_names = self._kin_char_model.get_body_names()
        self._mse_body_enabled = torch.ones((self.get_num_envs(), len(body_names), 1),
            device=self._device, dtype=torch.bool)
        self.disabled_leg_mse = dict(
            excluded_bodies_by_motion={
                'limpL': ['left_thigh', 'left_shin', 'left_foot'],
                'limpR': ['right_thigh', 'right_shin', 'right_foot'],
                'limpL_idle': ['left_thigh', 'left_shin', 'left_foot'],
                'limpR_idle': ['right_thigh', 'right_shin', 'right_foot']},
            terms=['position_mse', 'linear_velocity_mse', 'rotation_mse', 'angular_velocity_mse'],
            aggregation='excluded contributions zero; original 15-body denominator retained',
            flat_com_velocity_unchanged=True)
        # Precomputed powered-leg body mask for limp-row velocity weighting only.
        self._active_leg_bodies = torch.zeros((self.get_num_envs(), len(body_names), 1),
            device=self._device, dtype=torch.bool)
        for side, motion in [('right', 4), ('left', 5), ('right', 8), ('left', 9)]:
            worlds = (self._fixed_motion_ids == motion).nonzero().flatten()
            bodies = torch.tensor([body_names.index(side+'_'+part)
                for part in ('thigh', 'shin', 'foot')], device=self._device)
            self._active_leg_bodies[worlds[:, None], bodies[None, :]] = True
        assert not self._position_leeway, 'No position dead zone is enabled'
        self.disabled_dof_indices = {}
        for side, motion in [('left', 4), ('right', 5), ('left', 8), ('right', 9)]:
            indices = []
            for part in ('thigh', 'shin', 'foot'):
                joint = self._kin_char_model.get_joint(body_names.index(side + '_' + part))
                indices.extend(range(joint.dof_idx, joint.dof_idx + joint.get_dof_dim()))
            self.disabled_dof_indices[side] = indices
            world = (self._fixed_motion_ids == motion).nonzero().flatten()
            mask[world[:, None], torch.tensor(indices, device=self._device)[None, :]] = 0.
            bodies = torch.tensor([body_names.index(side+'_'+part)
                for part in ('thigh', 'shin', 'foot')], device=self._device)
            self._mse_body_enabled[world[:, None], bodies[None, :]] = False
        assert mask.shape == (self.get_num_envs(), 34)
        # Strength is physical-state conditioned on every row; identity only
        # controls the existing passive-leg mask, never the height multiplier.
        self.head_height_strength = dict(config['slow_loco_head_strength'])
        cfg = self.head_height_strength
        assert 0 <= cfg['vanilla_height_m'] < cfg['full_strength_height_m']
        self._head_id = body_names.index(cfg['head_body'])
        # Add twice the original head-only error: total head weight is3x,
        # with the original body/component denominator preserved.
        self._head_velocity_extra_weights = 2. * self._loss_weights[[1, 3]] / len(body_names)
        # Four extra copies plus the original =5x, throughout both limp episodes.
        # Fixed motion rows let us precompute the powered thigh/shin/foot mask.
        self._active_leg_velocity_extra = self._active_leg_bodies.to(self._loss_weights.dtype) * 4.

        self._head_offset = torch.tensor(cfg['head_offset_m'], device=self._device)
        self._motor_mask = mask
        self._motor_enabled_binary = mask.clone()
        base_caps = wp.to_torch(self._engine._uefn_motors.upper)
        self._maximum_motor_ratio = torch.ones_like(base_caps)
        for side in ('left', 'right'):
            for part in ('thigh', 'shin', 'foot'):
                joint = self._kin_char_model.get_joint(body_names.index(side + '_' + part))
                dofs = torch.arange(joint.dof_idx, joint.dof_idx + joint.get_dof_dim(), device=self._device)
                torch.testing.assert_close(base_caps[dofs], torch.full_like(base_caps[dofs], cfg['vanilla_nm'][part]))
                self._maximum_motor_ratio[dofs] = cfg['maximum_nm'][part] / base_caps[dofs]
        self.head_height_strength.update(
            vanilla_dof_torque_caps_nm=base_caps.cpu().tolist(),
            maximum_dof_torque_caps_nm=(base_caps*self._maximum_motor_ratio).cpu().tolist(),
            updated_before_each_control_step=True, control_dt_seconds=self._engine.get_timestep(),
            motor_velocity_gains_unchanged=True, ground_height_m=0., observation_size_unchanged=160)
        self.limp_support_strength = dict(hip_nm=400., knee_nm=500., ankle_nm=180.,
            scope='maximum at full head height, both enabled legs on every motion',
            disabled_leg_torque_nm=0., controller='head_height_strength')
        self._target_termination_enabled = torch.ones_like(self.target_distances_sq, dtype=torch.bool)
        self._target_radii_sq = torch.ones_like(self.target_distances_sq) * self._target_radius_sq
        limp = (self._limb_enabled[:,2:] == 0).any(-1)
        for side, limb_column in [('right', 2), ('left', 3)]:
            column = next(i for i, point in enumerate(self._termination_points) if point['body'] == side + '_foot')
            self._target_termination_enabled[:, column] = self._limb_enabled[:, limb_column] > 0
        # Double every target radius on limp rows, including the head.
        # The disabled foot remains excluded by its independent enable mask.
        self._target_radii_sq[limp] *= 4.
        # User-requested tighter hand spheres only for the two limp idles.
        for column, point in enumerate(self._termination_points):
            if point['body'] in ('left_hand', 'right_hand'):
                self._target_radii_sq[self._stationary_limp_idle[self._fixed_motion_ids], column] = .20**2
        # Pelvis follows the world reference, re-anchored every 70 ticks. Other spheres keep
        # their existing pelvis-XY-aligned targets and collider-centre offsets.
        self.world_pelvis_termination = True
        self._pelvis_id = body_names.index('pelvis')
        self._termination_points.append(dict(body='pelvis',offset=[0.,0.,0.],target_space='periodic_world_reference',shape='sphere'))
        self._termination_ids = torch.cat((self._termination_ids,torch.tensor([self._pelvis_id],device=self._device)))
        self._termination_offsets = torch.cat((self._termination_offsets,torch.zeros((1,3),device=self._device)))
        pelvis_radius_sq = torch.full_like(self._target_radius_sq.expand(self.get_num_envs()), .40**2)
        self._target_radii_sq = torch.cat((self._target_radii_sq,pelvis_radius_sq[:,None]),dim=1)
        self._target_termination_enabled = torch.cat((self._target_termination_enabled,torch.ones((self.get_num_envs(),1),device=self._device,dtype=torch.bool)),dim=1)
        self.target_distances_sq = torch.zeros_like(self._target_radii_sq)
        self._pelvis_window_steps = torch.full((len(names),), 70, device=self._device, dtype=torch.long)
        self._pelvis_window_steps[:2] = 130
        self._pelvis_window = PeriodicPelvisTarget(self._pelvis_window_steps[self._fixed_motion_ids], self._device)
        self._pelvis_target_world = self._pelvis_window.target

    def _update_head_strength(self):
        char = self._get_char_id()
        rotation = self._engine.get_body_rot(char)[:, self._head_id]
        offset = self._head_offset.expand(len(rotation), -1)
        self.actual_head_height = (self._engine.get_body_pos(char)[:, self._head_id]
            + torch_util.quat_rotate(rotation, offset))[:, 2]
        cfg = self.head_height_strength
        self.head_strength_fraction = strength_fraction(self.actual_head_height,
            cfg['vanilla_height_m'], cfg['full_strength_height_m'])
        self._motor_mask.copy_(torque_multipliers(self.actual_head_height,
            cfg['vanilla_height_m'], cfg['full_strength_height_m'],
            self._maximum_motor_ratio, self._motor_enabled_binary))

    def _pre_physics_step(self, actions):
        self._update_head_strength()
        super()._pre_physics_step(actions)

    def _reset_envs(self, env_ids):
        super()._reset_envs(env_ids)
        if hasattr(self, '_motor_enabled_binary'):
            self._update_head_strength()
        if hasattr(self, '_static_motion'):
            char = self._get_char_id()
            self._align_static_targets(self._engine.get_body_pos(char), self._engine.get_body_rot(char),
                self.reward_target_vel, self.reward_target_ang)
        if hasattr(self, '_pelvis_window'):
            self._pelvis_window.reset(env_ids,
                self._engine.get_body_pos(self._get_char_id())[env_ids, self._pelvis_id],
                self._ref_body_pos[env_ids, self._pelvis_id])


    def _reset_ref_motion(self, env_ids):
        if not getattr(self, '_motion_subset', None) and not getattr(self, '_crawl_only_experiment', False):
            return super()._reset_ref_motion(env_ids)
        motion_ids = self._fixed_motion_ids[env_ids]
        times = self._motion_lib.sample_time(motion_ids) if self._rand_reset else torch.zeros(len(env_ids), device=self._device)
        self._motion_ids[env_ids] = motion_ids
        self._motion_time_offsets[env_ids] = times
        values = self._motion_lib.calc_motion_frame(motion_ids, times)
        for destination, value in zip((self._ref_root_pos, self._ref_root_rot,
                self._ref_root_vel, self._ref_root_ang_vel, self._ref_joint_rot, self._ref_dof_vel), values):
            destination[env_ids] = value
        # Same reference-state setup as the pinned upstream DeepMimic reset.
        pos, rot = self._kin_char_model.forward_kinematics(self._ref_root_pos, self._ref_root_rot, self._ref_joint_rot)
        self._ref_body_pos.copy_(pos)
        self._ref_body_rot.copy_(rot)
        self._ref_dof_pos[env_ids] = self._motion_lib.joint_rot_to_dof(values[4])

    def _align_static_targets(self, pos, rot, target_vel, target_ang):
        static = self._static_motion[self._motion_ids]
        yaw = static_yaw_alignment(rot[:, 0], self._ref_body_rot[:, 0])
        identity = torch.zeros_like(yaw); identity[:, 3] = 1.
        yaw = torch.where(static[:, None], yaw, identity)[:, None]
        base = self._target_positions(pos, self._ref_body_pos)
        aligned_pos = torch_util.quat_rotate(yaw.expand_as(self._ref_body_rot), base-base[:, :1]) + base[:, :1]
        aligned_rot = torch_util.quat_mul(yaw.expand_as(self._ref_body_rot), self._ref_body_rot)
        self.reward_target_pos.copy_(torch.where(static[:, None, None], aligned_pos, base))
        self.reward_target_rot.copy_(torch.where(static[:, None, None], aligned_rot, self._ref_body_rot))
        # Static clips have no travel command. Keep vertical/articulation motion,
        # remove authored pelvis XY drift and rotate remaining vector targets.
        drift = torch.cat((self._ref_root_vel[:, :2], self._ref_root_vel[:, 2:]*0.), -1)
        aligned_vel = torch_util.quat_rotate(yaw.expand_as(self._ref_body_rot), target_vel-drift[:, None])
        aligned_ang = torch_util.quat_rotate(yaw.expand_as(self._ref_body_rot), target_ang)
        return (torch.where(static[:, None, None], aligned_vel, target_vel),
                torch.where(static[:, None, None], aligned_ang, target_ang))

    def _tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):
        target_vel, target_ang = self._align_static_targets(pos, rot, target_vel, target_ang)
        self.reward_target_vel.copy_(target_vel)
        self.reward_target_ang.copy_(target_ang)
        # Zero only the passive bodies' four imitation errors. Retain the same
        # reduction denominator, so each enabled body's contribution is unchanged.
        # The parent computes the separate COM objective from actual engine state.
        enabled = self._mse_body_enabled
        terms = super()._tracking_losses(
            torch.where(enabled, pos, self.reward_target_pos),
            torch.where(enabled, rot, self.reward_target_rot),
            torch.where(enabled, vel, target_vel),
            torch.where(enabled, ang, target_ang), target_vel, target_ang)
        terms[:, 1].add_((vel[:, self._head_id] - target_vel[:, self._head_id]).square().mean(-1)
            * self._head_velocity_extra_weights[0])
        terms[:, 3].add_((ang[:, self._head_id] - target_ang[:, self._head_id]).square().mean(-1)
            * self._head_velocity_extra_weights[1])
        terms[:, 1].add_(((vel-target_vel).square() * self._active_leg_velocity_extra).mean(dim=(1, 2))
            * self._loss_weights[1])
        terms[:, 3].add_(((ang-target_ang).square() * self._active_leg_velocity_extra).mean(dim=(1, 2))
            * self._loss_weights[3])
        if self._flat_com_config:
            terms[:, 4].masked_fill_(self._static_motion[self._motion_ids], 0.)
        return terms

    def _update_done(self):
        # Keep ordinary clip-end/timeout flags, then check only enabled targets.
        AbsoluteWalkEnv._update_done(self)
        ids = self._termination_ids
        char = self._get_char_id()
        termination_pos = self.reward_target_pos[:, ids].clone()
        actual = self._engine.get_body_pos(char)[:, self._pelvis_id]
        reference = self._ref_body_pos[:, self._pelvis_id].clone()
        # Idle breathing has no world travel heading: keep XY sphere anchor fixed
        # between recenters, while retaining the authored vertical reference.
        reference[:, :2] = torch.where(self._stationary_limp_idle[self._motion_ids,None],
            self._pelvis_window.reference_anchor[:, :2], reference[:, :2])
        self._pelvis_window.update(actual, reference)
        termination_pos[:, -1] = self._pelvis_target_world
        self.target_distances_sq.copy_(centre_distances(
            self._engine.get_body_pos(char)[:, ids], self._engine.get_body_rot(char)[:, ids],
            termination_pos, self.reward_target_rot[:, ids], self._termination_offsets))
        failed = ((self.target_distances_sq[:, :-1] > self._target_radii_sq[:, :-1]) & self._target_termination_enabled[:, :-1]).any(-1)
        failed |= self._pelvis_window.sphere_failed(actual) & self._target_termination_enabled[:, -1]
        exempt = (self._motion_ids == 2) | (self._motion_ids == 3)
        failed &= ~exempt
        self._done_buf[exempt & (self._done_buf == DoneFlags.FAIL.value)] = DoneFlags.NULL.value
        failed &= self._time_buf > 0
        self._done_buf[failed] = DoneFlags.FAIL.value
        # As in locomotion, reward is rebuilt before done on every control tick.
        # Charge once after classifying failure, before PPO/recorder copy it.
        # TIME and SUCC receive no charge; FAIL continuation value remains zero.
        if self.failure_penalty:
            self._reward_buf.sub_((self._done_buf == DoneFlags.FAIL.value).to(self._reward_buf.dtype) * self._failure_penalty_by_row)

    def _compute_obs(self, env_ids=None):
        physical = AbsoluteWalkEnv._compute_obs(self, env_ids)
        ids, phase = self._command_phase(env_ids)
        return torch.cat((physical, self._motion_onehot[ids], self._motion_limbs[ids], phase), -1)

    def replay_loss_metadata(self):
        result = super().replay_loss_metadata()
        result.update(task=self.task_name, motion_onehot_order=self.command_slots,
            limb_order=['right_arm', 'left_arm', 'right_leg', 'left_leg'],
            disabled_motor_dofs=self.disabled_dof_indices, perturbations=False, ae_reward=False,
            observation_contract='146 physical + 8 signed motion slots + 4 limb-enabled + 2 phase = 160',
            limb_semantics='0 = zero hip/knee/ankle motor torque, retaining contacts, mass and joint limits')
        result['motion_command_encoding'] = dict(version=1, slots=self.command_slots,
            vectors={n:self._motion_onehot[i].cpu().tolist() for i,n in enumerate(self.motion_labels)},
            semantics='Original eight +1 commands unchanged; limpL_idle=-1 in limpL slot, limpR_idle=-1 in limpR slot; all other slots zero',
            observation_channels_zero_based=[146,154], original_observation_size=160, new_observation_size=160)
        result['static_yaw_invariance'] = dict(
            motions=['crawl_idle', 'agonising', 'agonising_idle', 'lying', 'sitting', 'limpL_idle', 'limpR_idle'],
            alignment='world Z yaw only, best pelvis orientation alignment',
            position_rotation_and_articulation_velocity=True,
            flat_com_velocity_disabled=True, reference_pelvis_xy_velocity_removed=True,
            pitch_roll_height_preserved=True, limb_termination_targets_aligned=True,
            moving_motions_unchanged=True)
        result['objective'] = 'Four body MSEs; static motions world-Z-yaw invariant, moving motions original world targets'
        result['loco_failure_penalty'] = self.failure_penalty
        result['terminal_meaning'] = '1=failure: one-time reward subtraction of loco_failure_penalty, zero bootstrap; 3=timeout without penalty'
        result['target_deviation']['disabled_leg_foot_exempt'] = True
        result['motion_sampling'] = self.motion_sampling.copy()
        result['limp_support_strength'] = self.limp_support_strength.copy()
        result['head_height_strength'] = self.head_height_strength.copy()
        result['head_velocity_mse'] = dict(body='head', scope='all motions and rows',
            linear_velocity_multiplier=3., angular_velocity_multiplier=3.,
            position_multiplier=1., rotation_multiplier=1.,
            normalization='original body/component mean; other body contributions unchanged')

        result['disabled_leg_mse'] = self.disabled_leg_mse.copy()
        result['active_leg_velocity_mse'] = dict(
            affected_bodies_by_motion=dict(limpL=['right_thigh','right_shin','right_foot'],
                                          limpR=['left_thigh','left_shin','left_foot'],
                                          limpL_idle=['right_thigh','right_shin','right_foot'],
                                          limpR_idle=['left_thigh','left_shin','left_foot']),
            linear_velocity_multiplier=5., angular_velocity_multiplier=5.,
            scope='whole episode; no stance, phase or contact gating',
            normalization='original body/component mean; four extra copies plus original',
            position_rotation_unchanged=True, disabled_leg_still_excluded=True)
        result['active_leg_position_leeway'] = dict(enabled=False, radius_m=0., shape='sphere',
            affected_bodies_by_motion=dict(limpL=['right_thigh','right_shin','right_foot'],
                                          limpR=['left_thigh','left_shin','left_foot'],
                                          limpL_idle=['right_thigh','right_shin','right_foot'],
                                          limpR_idle=['left_thigh','left_shin','left_foot']),
            formula='ordinary squared position error; no dead zone',
            term='position_mse only', velocity_rotation_unchanged=True,
            termination_spheres_unchanged=True, disabled_leg_still_excluded=True)
        result['active_leg_rotation_leeway'] = dict(enabled=False, angle_degrees=0.,
            affected_bodies_by_motion=dict(limpL=['right_thigh','right_shin','right_foot'],
                                          limpR=['left_thigh','left_shin','left_foot'],
                                          limpL_idle=['right_thigh','right_shin','right_foot'],
                                          limpR_idle=['left_thigh','left_shin','left_foot']),
            formula='ordinary rotation-matrix MSE; no dead zone',
            normalization='original body/matrix-component denominator and calibrated weight',
            term='rotation_mse only', position_leeway_m=0.,
            linear_angular_velocity_unchanged=True, termination_spheres_unchanged=True,
            disabled_leg_still_excluded=True)
        result['target_deviation']['limp_foot_radius_m'] = 2 * self.target_radius_m
        result['target_deviation']['limp_hand_radius_m'] = 2 * self.target_radius_m
        result['target_deviation']['limp_idle_hand_radius_m'] = .20
        result['target_deviation']['limp_head_radius_m'] = 2 * self.target_radius_m
        result['target_deviation']['world_pelvis'] = dict(body='pelvis',point='body origin',axes='world XYZ, Z vertical',
            target='original reference displacement from actual pelvis XY anchor, refreshed every70 ticks; absolute reference Z',
            stationary_xy_motions=['limpL_idle','limpR_idle'], reset_every_ticks=70, base_radius_m=.40, radius_formula='constant 0.40 metres',
            horizontal_warmup='none; sphere checked from first tick',
            steps_by_motion=dict(zip(self.motion_labels,self._pelvis_window_steps.cpu().tolist())),
            shape='sphere', recenter_axes='XY only', check_on_recenter='recenter first, then check full sphere')
        result['target_deviation']['comparison'] = 'head/hand/foot spheres unchanged; fixed40cm pelvis world sphere, re-anchored every70 ticks'
        result['target_deviation']['radius_by_motion_m'] = {
            name: {point['body']: (None if
                name in ('agonising', 'agonising_idle') or
                (name.startswith('limpL') and point['body'] == 'left_foot') or
                (name.startswith('limpR') and point['body'] == 'right_foot') else
                (.40 if point['body']=='pelvis' else .20 if name in ('limpL_idle','limpR_idle') and point['body'] in ('left_hand','right_hand') else self.target_radius_m * (2 if name.startswith('limp') else 1)))
                for point in self._termination_points}
            for name in self.motion_labels}
        result['motion_loop_modes'] = {name: int(mode) for name, mode in zip(self.motion_labels, self._motion_lib._motion_loop_modes.cpu().tolist())}
        return result
