"""Opt-in normal/perturbed curriculum with a frozen motion prior."""
import json
import math
import hashlib
import numpy as np
import xml.etree.ElementTree as ET
from pathlib import Path
import torch
import warp as wp
from envs.base_env import DoneFlags, EnvMode
from util import torch_util as q
from recovery_omni import RecoveryOmniEnv, random_start_rows
from omni_walk import phase_at
from omni_policy import circular_phase
from absolute_walk import world_velocities, aligned_positions
from perturbed_motion import MotionPrior, COM2_BODIES, com2_velocity, yaw_matrix, yaw_velocities_preserving_com2, com2_failure, tracking_blend
from perturbed_motion import getup_head_height_loss, getup_head_height_reward


@torch.jit.script
def getup_pelvis_horizontal_cost(velocity: torch.Tensor, limit: torch.Tensor):
    # Physics is Z-up. velocity is world-space BODY ORIGIN velocity, not COM.
    return (velocity[..., :2].norm(p=2, dim=-1)-limit).clamp_min(0.).square()


@torch.jit.script
def getup_foot_costs(command: torch.Tensor, foot_rot: torch.Tensor,
                    calf_rot: torch.Tensor, idle_local: torch.Tensor):
    # Physical commanded ankle angular velocity, after the environment clamp.
    speed = command.square().mean(-1)
    local = q.quat_mul(q.quat_conjugate(calf_rot), foot_rot)
    delta = q.quat_mul(q.quat_conjugate(idle_local), local)
    # Shortest rotation angle; q and -q are the same orientation.
    angle = 2. * torch.atan2(delta[..., :3].norm(p=2, dim=-1), delta[..., 3].abs())
    return torch.stack((speed, angle.square().mean(-1)), -1)


def sample_getup_plus_velocities(root_pool, dof_pool, count, max_spin):
    """Separate source frames, isotropic axis, uniform angular speed in radians/s."""
    size = len(root_pool)
    a = torch.randint(size, (count,), device=root_pool.device)
    b = torch.randint(size-1, (count,), device=root_pool.device)
    b = b + (b >= a).long()
    axis = torch.randn((count, 3), device=root_pool.device)
    axis = axis / axis.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    spin = axis * (torch.rand((count, 1), device=root_pool.device) * max_spin)
    return root_pool[a], dof_pool[b], spin, a, b


def getup_pelvis_failure(perturbed_getup, ticks, pelvis_height, ceiling, grace_ticks):
    return perturbed_getup & (ticks > grace_ticks) & (pelvis_height >= ceiling)


def getup_success_stability(feet_height, head_vertical_velocity, feet_limit, speed_limit):
    """World-Z body-origin measurements, strict bounds; no extra physics steps."""
    return (feet_height < feet_limit).all(dim=-1) & (head_vertical_velocity.abs() < speed_limit)


def blend_root_pose(position, rotation, target_position, target_rotation, alpha):
    """Linear root translation and shortest-arc quaternion interpolation."""
    a = alpha[:, None]
    dot = (rotation * target_rotation).sum(-1, keepdim=True)
    target_rotation = torch.where(dot < 0, -target_rotation, target_rotation)
    dot = dot.abs().clamp(0, 1)
    angle = torch.acos(dot.clamp_max(1-1e-7))
    spherical = (torch.sin((1-a)*angle)*rotation + torch.sin(a*angle)*target_rotation) / torch.sin(angle)
    linear = rotation + a*(target_rotation-rotation)
    result = torch.where(dot > .9995, linear, spherical)
    return position + a*(target_position-position), result / result.norm(dim=-1, keepdim=True).clamp_min(1e-8)


def floor_support_points(model_path, names, device):
    """Box corners and capsule/sphere centres; exact support against flat Z=0."""
    import itertools
    from scipy.spatial.transform import Rotation
    points, radii, ids = [], [], []
    for body in ET.parse(model_path).iter('body'):
        if body.get('name') not in names:
            continue
        for geom in body.findall('geom'):
            kind = geom.get('type')
            size = np.fromstring(geom.get('size'), sep=' ')
            position = np.fromstring(geom.get('pos', '0 0 0'), sep=' ')
            rotation = Rotation.from_quat(np.roll(np.fromstring(geom.get('quat', '1 0 0 0'), sep=' '), -1))
            if kind == 'box':
                local = np.array(list(itertools.product([-1, 1], repeat=3))) * size
                radius = 0.
            elif kind == 'capsule':
                local = np.array([[0., 0., -size[1]], [0., 0., size[1]]])
                radius = size[0]
            elif kind == 'sphere':
                local = np.zeros((1, 3))
                radius = size[0]
            else:
                raise ValueError('Unsupported reset floor collider: '+str(kind))
            points.extend(rotation.apply(local)+position)
            radii.extend([radius]*len(local))
            ids.extend([names.index(body.get('name'))]*len(local))
    if set(ids) != set(range(len(names))):
        raise ValueError('Reset floor support missing a body collider')
    return (torch.tensor(ids, dtype=torch.long, device=device),
            torch.tensor(np.asarray(points), dtype=torch.float32, device=device),
            torch.tensor(radii, dtype=torch.float32, device=device))


def floor_reset_lift(body_pos, body_rot, support):
    ids, points, radii = support
    rotations = body_rot[:, ids]
    world = body_pos[:, ids] + q.quat_rotate(rotations, points.expand(*rotations.shape[:-1], 3))
    minimum = (world[:, :, 2]-radii).amin(dim=1)
    # A two-micrometre float32 allowance, applied only to penetrating starts.
    return torch.where(minimum < 0, -minimum+2e-6, torch.zeros_like(minimum))


class PerturbedOmniEnv(RecoveryOmniEnv):
    def __init__(self, *args, **kwargs):
        self._perturb_ready = False
        super().__init__(*args, **kwargs)
        from batched_joint_conversion import install
        install(self._kin_char_model)
        if (str(self._device).startswith('cuda') and self._equipment_conditioning
                and not self._enable_phase_obs and not self._enable_tar_obs):
            from graphed_observations import install as install_observations
            install_observations(self)

    def _build_sim_tensors(self, config):
        super()._build_sim_tensors(config)
        cfg = config['perturbed_motion']
        self._perturb_cfg = dict(cfg)
        self._mse_only = bool(cfg.get('mse_only', False))
        self._idle_position_getup = cfg.get('getup_objective') == 'idle_frame0_body_positions'
        self._getup_position_weight = float(cfg.get('getup_position_mse_weight', 1.))
        self._getup_reward_form = cfg.get('getup_position_reward_form', 'reciprocal_sum')
        if self._getup_reward_form not in ('reciprocal_sum', 'linear_cost'):
            raise ValueError('Unknown perturbed get-up position reward')
        self._getup_blend = cfg.get('getup_pose_blend') == 'uniform_0_1'
        self._getup_upper_half_probability = float(cfg.get('getup_upper_half_probability', .5))
        if not 0 < self._getup_upper_half_probability < 1:
            raise ValueError('Get-up upper-half probability must be between zero and one')
        n = self.get_num_envs()
        # Preserve idle-first layout used by fixed assignments and the recorder.
        normal = round(n*(1-float(cfg['fraction'])))
        normal_idle = round(normal*float(config['idle_row_fraction']))
        self._perturbed_rows = torch.ones(n, dtype=torch.bool, device=self._device)
        for start, count, keep in ((0, self._idle_rows, normal_idle),
                                   (self._idle_rows, n-self._idle_rows, normal-normal_idle)):
            if keep:
                ids = start + torch.floor((torch.arange(keep, device=self._device)+.5)*count/keep).long()
                self._perturbed_rows[ids] = False
        # Temporary user-requested get-up rehearsal; all other cohort assignments
        # remain identical. Removing this flag restores the original 30/70 mask.
        if cfg.get('getup_normal_only', False):
            self._perturbed_rows[self._recovery_rows] = False
        if cfg.get('getup_limp_dataset'):
            getups = torch.where(self._recovery_rows)[0]
            keep = int((~self._perturbed_rows[getups]).sum())
            if len(getups):
                balanced_normal = random_start_rows(getups, n, keep/len(getups), self._recovery_fixed_motion)
                self._perturbed_rows[getups] = ~balanced_normal[getups]
        self._perturbed_ids = torch.where(self._perturbed_rows)[0]
        self._perturbed_getup = self._perturbed_rows & self._recovery_rows
        if 'normal_getup_random_start_fraction' in cfg:
            normal_getups = torch.where(self._recovery_rows & ~self._perturbed_rows)[0]
            self._recovery_random_start_rows = random_start_rows(
                normal_getups, n, float(cfg['normal_getup_random_start_fraction']),
                self._recovery_fixed_motion)
        # Optional additive prior regularizes perturbed get-ups without replacing MSE.
        prior_rows = self._perturbed_rows & ~self._perturbed_getup if self._idle_position_getup else self._perturbed_rows
        if cfg.get('getup_ae_regularizer', False):
            prior_rows |= self._perturbed_getup
        if self._mse_only:
            prior_rows = torch.zeros_like(prior_rows)
        self._prior_ids = torch.where(prior_rows)[0]
        self._recovery_random_start_rows[self._perturbed_getup] = False
        self._phase_feedback_ids = torch.where(self._perturbed_rows | self._recovery_rows)[0]
        self._phase_supervision_mask = (~(self._perturbed_rows | self._recovery_rows)).float()
        self._prior_index = torch.full((n,), -1, dtype=torch.long, device=self._device)
        self._prior_index[self._prior_ids] = torch.arange(len(self._prior_ids), device=self._device)
        names = self._kin_char_model.get_body_names()
        self._limp_dofs = None
        self._limp_floor_support = None
        if cfg.get('getup_limp_dataset'):
            path = Path(cfg['getup_limp_dataset'])
            if hashlib.sha256(path.read_bytes()).hexdigest() != cfg['getup_limp_sha256']:
                raise ValueError('Limp initialization corpus checksum mismatch')
            with np.load(path, allow_pickle=False) as data:
                if data['body_names'].tolist() != names:
                    raise ValueError('Limp initialization body order differs from simulator')
                arrays = [data[k].copy() for k in ('dof', 'root_position', 'root_quaternion_xyzw')]
            expected = [(1000, self._ref_dof_pos.shape[-1]), (1000, 3), (1000, 4)]
            if any(x.shape != shape or not np.isfinite(x).all() for x, shape in zip(arrays, expected)):
                raise ValueError('Invalid limp initialization corpus dimensions or values')
            if not np.allclose(np.linalg.norm(arrays[2], axis=-1), 1., atol=1e-5):
                raise ValueError('Invalid limp root quaternion')
            self._limp_dofs, self._limp_root_pos, self._limp_root_rot = [
                torch.as_tensor(x, dtype=torch.float32, device=self._device) for x in arrays]
            if cfg.get('getup_floor_clearance_after_blend'):
                self._limp_floor_support = floor_support_points(cfg['getup_floor_model'], names, self._device)
        if not self._mse_only:
            contract = json.loads((Path(cfg['ae_directory'])/'body_contract.json').read_text())
            if names != contract['body_names']:
                raise ValueError('AE body order differs from simulator')
        self._com2_ids = torch.tensor([names.index(x) for x in COM2_BODIES], device=self._device)
        masses = wp.to_torch(self._engine._sim_model.body_mass).view(n, -1)[0, self._com2_ids]
        self._com2_masses = masses/masses.sum()
        table = json.loads(Path(cfg['com2_targets']).read_text())
        entries = {r['id']: r for r in table['motions']}
        targets = [entries[Path(self._motion_lib.get_motion_file(i)).stem]['average_xy_m_s']
                   for i in range(self._motion_lib.get_num_motions())]
        self._com2_targets = torch.tensor(targets, device=self._device)
        self._extremity_speed_enabled = bool(cfg.get('extremity_speed_reference'))
        if self._extremity_speed_enabled:
            speed_table = json.loads(Path(cfg['extremity_speed_reference']).read_text())
            speed_names = speed_table['bodies']
            self._extremity_speed_ids = torch.tensor([names.index('pelvis')] + [names.index(n) for n in speed_names], device=self._device)
            entries_speed = {r['id']: r for r in speed_table['motions']}
            limits = [entries_speed[Path(self._motion_lib.get_motion_file(i)).stem]['limits_m_s'] for i in range(self._motion_lib.get_num_motions())]
            self._extremity_speed_limits = torch.tensor(limits, device=self._device)
            if not torch.isfinite(self._extremity_speed_limits).all() or (self._extremity_speed_limits < 0).any():
                raise ValueError('Invalid extremity speed reference limits')
            self._extremity_speed_limits_sq = self._extremity_speed_limits.square()
        torch.testing.assert_close(masses, torch.tensor(table['masses_kg'], device=self._device))
        if not torch.isfinite(self._com2_targets).all():
            raise ValueError('Invalid precomputed COM2 target')
        ids = torch.arange(self._motion_lib.get_num_motions(), device=self._device)
        root, rot, _, _, joints, _ = self._motion_lib.calc_motion_frame(ids, torch.zeros_like(ids, dtype=torch.float32))
        pos, body_rot = self._kin_char_model.forward_kinematics(root, rot, joints)
        self._idle_frame0_pos = pos.clone()
        self._idle_frame0_rot = body_rot.clone()
        pelvis_cfg = cfg.get('getup_pelvis_horizontal_regularizer')
        self._pelvis_horizontal_enabled = pelvis_cfg is not None
        if self._pelvis_horizontal_enabled:
            if names[0] != 'pelvis' or not self._idle_position_getup:
                raise ValueError('Pelvis speed cost requires pelvis-first idle-position get-ups')
            gravity = torch.as_tensor(self._engine.get_gravity(), device=self._device)
            torch.testing.assert_close(gravity[:2], torch.zeros(2, device=self._device))
            if not gravity[2] < 0:
                raise ValueError('Expected world Z-up physics')
            lib = self._recovery_lib
            limits = []
            for motion in range(lib.get_num_motions()):
                entry = pelvis_cfg['motions'][Path(lib.get_motion_file(motion)).stem]
                start = int(lib._motion_start_idx[motion])
                count = int(lib._motion_num_frames[motion])
                peak = lib._frame_root_vel[start:start+count, :2].norm(p=2, dim=-1).max()
                limit = float(entry['peak_horizontal_m_s'])
                torch.testing.assert_close(peak, torch.tensor(limit, device=self._device), atol=1e-6, rtol=1e-6)
                limits.append(limit)
            # Either get-up can roll into the other: one common peak for all rows.
            self._pelvis_horizontal_limits = torch.full((len(limits),), max(limits), device=self._device)
            self._pelvis_horizontal_weight = float(pelvis_cfg['weight'])
            if not math.isfinite(self._pelvis_horizontal_weight) or self._pelvis_horizontal_weight <= 0:
                raise ValueError('Pelvis horizontal weight must be finite and positive')
        foot_cfg = cfg.get('getup_foot_regularizers')
        self._foot_regularizers_enabled = foot_cfg is not None
        if self._foot_regularizers_enabled:
            if not self._idle_position_getup:
                raise ValueError('Foot regularizers require the idle-frame0 get-up objective')
            self._foot_cost_ids = [names.index('left_foot'), names.index('right_foot')]
            self._foot_calf_ids = [int(self._kin_char_model.get_parent_id(i)) for i in self._foot_cost_ids]
            if [names[i] for i in self._foot_calf_ids] != ['left_shin', 'right_shin']:
                raise ValueError('Expected each foot parent to be its calf')
            indices = []
            for i in self._foot_cost_ids:
                start = self._kin_char_model.get_joint_dof_idx(i)
                if self._kin_char_model.get_joint_dof_dim(i) != 3:
                    raise ValueError('Expected three velocity commands per ankle')
                indices.extend(range(start, start+3))
            self._foot_command_ids = indices
            self._foot_idle_local = q.quat_mul(q.quat_conjugate(body_rot[:, self._foot_calf_ids]), body_rot[:, self._foot_cost_ids])
            weights = [float(foot_cfg[k]) for k in ('velocity_weight', 'rotation_weight')]
            if not all(math.isfinite(w) and w > 0 for w in weights):
                raise ValueError('Foot loss weights must be finite and positive')
            self._foot_cost_weights = torch.tensor(weights, device=self._device)
        # Keep reward/display orientations separate from the spawn reference.
        self.reward_target_rot = self._ref_body_rot.clone()
        self._head_id = names.index('head')
        self._pelvis_ceiling_id = names.index('pelvis')
        self._pelvis_ceiling = cfg.get('getup_failure_pelvis_height_m')
        if self._pelvis_ceiling is not None and not (math.isfinite(float(self._pelvis_ceiling)) and self._pelvis_ceiling > 0):
            raise ValueError('Pelvis failure height must be finite and positive')
        self._idle_head_height = pos[:, self._head_id, 2]
        self._head_reset_height = self._idle_head_height * float(cfg['getup_head_reset_fraction'])
        self._success_feet_ids = [names.index('left_foot'), names.index('right_foot')]
        self._success_feet_limit = cfg.get('getup_success_max_feet_height_m')
        self._success_speed_limit = cfg.get('getup_success_max_head_vertical_speed_m_s')
        if (self._success_feet_limit is None) != (self._success_speed_limit is None):
            raise ValueError('Get-up success feet and head-speed limits must be configured together')
        if self._success_feet_limit is not None:
            if not all(math.isfinite(float(v)) and float(v) > 0 for v in (self._success_feet_limit, self._success_speed_limit)):
                raise ValueError('Get-up success limits must be finite and positive')
        # Uniform frames over every locomotion clip, including both D/S variants.
        starts = self._motion_lib._motion_start_idx
        eligible = []
        for i in torch.where(self._gaits != -1)[0].tolist():
            eligible.append(torch.arange(int(starts[i]), int(starts[i]+self._motion_lib._motion_num_frames[i]), device=self._device))
        self._loco_frame_pool = torch.cat(eligible)
        self._loco_reset_dofs = self._motion_lib.joint_rot_to_dof(self._motion_lib._frame_joint_rot[self._loco_frame_pool])
        plus_fraction = float(cfg.get('getup_plus_fraction', 0.))
        self._perturbed_plus = random_start_rows(torch.where(self._perturbed_getup)[0],
            n, plus_fraction, self._recovery_fixed_motion)
        self._getup_low_head_ticks = torch.where(self._perturbed_plus,
            int(cfg.get('getup_plus_low_head_failure_tick', cfg['getup_low_head_failure_tick'])),
            int(cfg['getup_low_head_failure_tick']))
        self._plus_max_spin = math.radians(float(cfg.get('getup_plus_max_spin_degrees_s', 700.)))
        if not math.isfinite(self._plus_max_spin) or self._plus_max_spin < 0:
            raise ValueError('Invalid perturbed+ spin bound')
        self._plus_root_pool = self._motion_lib._frame_root_vel[self._loco_frame_pool]
        self._plus_dof_pool = self._motion_lib._frame_dof_vel[self._loco_frame_pool]
        if len(self._plus_root_pool) < 2 or not torch.isfinite(self._plus_root_pool).all() or not torch.isfinite(self._plus_dof_pool).all():
            raise ValueError('Invalid locomotion velocity pool')
        self._plus_linear_frame = torch.full((n,), -1, dtype=torch.long, device=self._device)
        self._plus_joint_frame = torch.full_like(self._plus_linear_frame, -1)
        self._plus_root_velocity = torch.zeros((n, 3), device=self._device)
        self._plus_spin = torch.zeros_like(self._plus_root_velocity)
        self._yaw_degrees = torch.zeros(n, device=self._device)
        self._initial_com2 = torch.zeros((n, 2), device=self._device)
        self._initial_com2_error = torch.zeros(n, device=self._device)
        self._random_pose_frame = torch.full((n,), -1, dtype=torch.long, device=self._device)
        self._pose_blend = torch.ones(n, device=self._device)
        self._reset_floor_lift = torch.zeros(n, device=self._device)
        self._prior = None if self._mse_only else MotionPrior(cfg['ae_directory'], len(self._prior_ids), self._device)
        self._ae_weight = 0. if self._mse_only else float(cfg['ae_weight'])
        if not self._mse_only and (not math.isfinite(self._ae_weight) or self._ae_weight <= 0):
            raise ValueError('AE weight must be finite and positive')
        self._prior_raw = torch.zeros(n, device=self._device)
        self._tracking_mix = torch.ones(n, device=self._device)
        pelvis_scale = float(cfg.get('all_rows_pelvis_velocity_mse_multiplier', 1.))
        if not math.isfinite(pelvis_scale) or pelvis_scale <= 0:
            raise ValueError('Pelvis velocity MSE multiplier must be finite and positive')
        idle_scale = float(cfg.get('idle_pose_mse_multiplier', 1.))
        if not math.isfinite(idle_scale) or idle_scale <= 0:
            raise ValueError('Perturbed idle pose MSE multiplier must be finite and positive')
        early_weight = float(cfg.get('ae_mse_weight', 0.))
        if not math.isfinite(early_weight) or early_weight < 0:
            raise ValueError('Early AE-associated MSE weight must be finite and nonnegative')
        self._reset_reason = torch.zeros(n, device=self._device, dtype=torch.long)
        self._outcome_ends = torch.zeros(n, device=self._device, dtype=torch.long)
        self._outcome_failures = torch.zeros_like(self._outcome_ends)
        self._outcome_head_resets = torch.zeros_like(self._outcome_ends)
        self._ae_diagnostics = torch.zeros(2, device=self._device)
        self._additive_head_reward = not self._idle_position_getup and cfg.get('getup_head_reward_form') == 'linear_height_additive'
        self._head_height_reward = torch.zeros(n, device=self._device)
        self._reward_diagnostics = torch.zeros(4, device=self._device)
        self.loss_term_names = (*self.loss_term_names, 'motion_prior')
        self.loss_weights['motion_prior'] = self._ae_weight
        if not self._additive_head_reward and not self._idle_position_getup:
            self.loss_term_names = (*self.loss_term_names, 'getup_head_height')
            self.loss_weights['getup_head_height'] = float(cfg['getup_head_height_weight'])
        speed_weight = float(cfg.get('extremity_speed_loss_weight', 0.))
        if not math.isfinite(speed_weight) or speed_weight < 0:
            raise ValueError('Extremity speed loss weight must be finite and nonnegative')
        if speed_weight:
            if not self._extremity_speed_enabled:
                raise ValueError('Extremity speed loss requires reference limits')
            self.loss_term_names = (*self.loss_term_names, 'extremity_speed_excess')
            self.loss_weights['extremity_speed_excess'] = speed_weight
        if self._foot_regularizers_enabled:
            self.loss_term_names = (*self.loss_term_names, 'feet_target_velocity', 'feet_idle_local_rotation')
            self.loss_weights['feet_target_velocity'] = weights[0]
            self.loss_weights['feet_idle_local_rotation'] = weights[1]
        if self._pelvis_horizontal_enabled:
            self.loss_term_names = (*self.loss_term_names, 'pelvis_horizontal_speed_excess')
            self.loss_weights['pelvis_horizontal_speed_excess'] = self._pelvis_horizontal_weight
        self.loss_terms = torch.zeros((n, len(self.loss_term_names)), device=self._device)
        self._completed_loss_totals = torch.zeros(len(self.loss_term_names)+1, device=self._device)
        self._perturb_ready = True

    def _reset_ref_motion(self, env_ids):
        super()._reset_ref_motion(env_ids)
        if not self._perturb_ready:
            return
        ids = env_ids[self._perturbed_rows[env_ids] & ~self._recovery_rows[env_ids]]
        motion = self._motion_ids[ids]
        phase = phase_at(self._time_buf[ids]+self._motion_time_offsets[ids],
            self._motion_lib.get_motion_length(motion), self._phase_offsets[motion])
        self._feedback_phase[ids] = phase
        self._pending_phase[ids] = phase

    def _target_positions(self, actual, reference, env_ids=None):
        target = super()._target_positions(actual, reference, env_ids)
        if not self._perturb_ready or not self._idle_position_getup:
            return target
        motion = self._motion_ids if env_ids is None else self._motion_ids[env_ids]
        mask = self._perturbed_getup if env_ids is None else self._perturbed_getup[env_ids]
        idle = aligned_positions(actual, self._idle_frame0_pos[motion])
        return torch.where(mask[:, None, None], idle, target)

    def _refresh_reward_rotations(self):
        self.reward_target_rot.copy_(self._ref_body_rot)
        if self._idle_position_getup:
            rows = self._perturbed_getup
            self.reward_target_rot[rows] = self._idle_frame0_rot[self._motion_ids[rows]]
            self.reward_target_vel[rows] = 0.
            self.reward_target_ang[rows] = 0.

    def _ref_state_init(self, env_ids):
        super()._ref_state_init(env_ids)
        if not self._perturb_ready:
            return
        e, char = self._engine, self._get_char_id()
        self._reset_floor_lift[env_ids] = 0.
        getup = env_ids[self._perturbed_getup[env_ids]]
        pool = self._loco_reset_dofs if self._limp_dofs is None else self._limp_dofs
        sample = torch.randint(len(pool), (len(getup),), device=self._device)
        target = pool[sample]
        alpha = torch.ones(len(getup), device=self._device)
        if self._getup_blend:
            # One strength per episode for every joint and, for limp starts,
            # the root transform below.
            base = e.get_dof_pos(char)[getup]
            alpha = torch.rand(len(getup), device=self._device)
            # Inverse CDF: uniform within each half, with configurable mass.
            # Keep the old uniform path bit-identical and consume no extra RNG.
            p = self._getup_upper_half_probability
            if p != .5:
                alpha = torch.where(alpha < 1-p, .5*alpha/(1-p),
                                    .5 + .5*(alpha-(1-p))/p)
            target = base + alpha[:, None] * (target-base)
            self._pose_blend[getup] = alpha
        e.set_dof_pos(getup, char, target)
        if self._limp_dofs is not None:
            root, rotation = blend_root_pose(e.get_root_pos(char)[getup], e.get_root_rot(char)[getup],
                self._limp_root_pos[sample], self._limp_root_rot[sample], alpha)
            if self._limp_floor_support is not None:
                pos, rot = self._kin_char_model.forward_kinematics(root, rotation,
                    self._kin_char_model.dof_to_rot(target))
                lift = floor_reset_lift(pos, rot, self._limp_floor_support)
                root[:, 2] += lift
                self._reset_floor_lift[getup] = lift
            e.set_root_pos(getup, char, root)
            e.set_root_rot(getup, char, rotation)
            # Preserve the authored starting velocities; this corpus supplies poses.
            self._random_pose_frame[getup] = sample
        else:
            self._random_pose_frame[getup] = self._loco_frame_pool[sample]
        plus = env_ids[self._perturbed_plus[env_ids]]
        if len(plus):
            linear, dof, spin, a, b = sample_getup_plus_velocities(
                self._plus_root_pool, self._plus_dof_pool, len(plus), self._plus_max_spin)
            # Animation translation is at the pelvis origin. Newton free-root
            # linear velocity is at its COM; account for the new independent spin.
            offset = q.quat_rotate(e.get_root_rot(char)[plus], self._body_com[plus, 0])
            e.set_root_vel(plus, char, linear + torch.cross(spin, offset, dim=-1))
            e.set_root_ang_vel(plus, char, spin)
            e.set_dof_vel(plus, char, dof)
            self._plus_linear_frame[plus] = self._loco_frame_pool[a]
            self._plus_joint_frame[plus] = self._loco_frame_pool[b]
            self._plus_root_velocity[plus] = linear
            self._plus_spin[plus] = spin
        self._yaw_degrees[env_ids] = 0.
        ids = env_ids[self._perturbed_rows[env_ids] & ~self._recovery_rows[env_ids]]
        if not len(ids):
            return
        angle = (torch.rand(len(ids), device=self._device)*2-1)*float(self._perturb_cfg['yaw_degrees'])*math.pi/180
        self._yaw_degrees[ids] = angle*180/math.pi
        root_pos = e.get_root_pos(char)[ids]
        root_rot = e.get_root_rot(char)[ids]
        root_vel = e.get_root_vel(char)[ids]
        root_ang = e.get_root_ang_vel(char)[ids]
        joints = self._kin_char_model.dof_to_rot(e.get_dof_pos(char)[ids])
        pos, rot = self._kin_char_model.forward_kinematics(root_pos, root_rot, joints)
        local = (e.get_dof_vel(char)[ids]@self._velocity_mapping).view(len(ids), -1, 3)
        # Newton root velocity refers to the pelvis COM, while FK refers to origins.
        origin_velocity = root_vel - torch.cross(root_ang, q.quat_rotate(root_rot, self._body_com[ids, 0]), dim=-1)
        v, w = world_velocities(pos, rot, origin_velocity, root_ang, local, self._velocity_parents)
        com_velocity = v + torch.cross(w, q.quat_rotate(rot, self._body_com[ids]), dim=-1)
        self._initial_com2[ids] = com2_velocity(com_velocity[:, self._com2_ids], self._com2_masses)
        turned, angular = yaw_velocities_preserving_com2(com_velocity, w, yaw_matrix(angle), self._com2_ids, self._com2_masses)
        yaw = torch.zeros((len(ids), 4), device=self._device)
        yaw[:, 2] = torch.sin(angle*.5); yaw[:, 3] = torch.cos(angle*.5)
        e.set_root_rot(ids, char, q.quat_mul(yaw, root_rot))
        e.set_root_vel(ids, char, turned[:, 0])
        e.set_root_ang_vel(ids, char, angular[:, 0])

    def _reset_envs(self, env_ids):
        super()._reset_envs(env_ids)
        if not self._perturb_ready:
            return
        ids = env_ids[self._prior_index[env_ids] >= 0]
        char = self._get_char_id()
        if self._prior is not None and len(ids):
            self._prior.reset(self._prior_index[ids], self._engine.get_body_pos(char)[ids],
                q.quat_to_matrix(self._engine.get_body_rot(char)[ids]))
        self._prior_raw[env_ids] = 0.
        self._head_height_reward[env_ids] = 0.
        self._reset_reason[env_ids] = 0
        self._tracking_mix[env_ids] = (~self._perturbed_rows[env_ids]).float()
        self._refresh_reward_rotations()
        yaw_ids = env_ids[self._perturbed_rows[env_ids] & ~self._recovery_rows[env_ids]]
        actual = com2_velocity(self._engine.get_body_vel(char)[yaw_ids][:, self._com2_ids], self._com2_masses)
        self._initial_com2_error[yaw_ids] = (actual-self._initial_com2[yaw_ids]).norm(dim=-1)

    def queue_phase_prediction(self, prediction):
        ids = self._phase_feedback_ids
        fallback = self._feedback_phase[ids]
        length = prediction.norm(dim=-1, keepdim=True)
        self._pending_phase[ids] = torch.where(length > 1e-6, prediction/length.clamp_min(1e-6), fallback)

    def step(self, action):
        if self._perturb_ready:
            self._feedback_phase[self._phase_feedback_ids] = self._pending_phase[self._phase_feedback_ids]
        return super().step(action)

    def _get_motion_times(self, env_ids=None):
        times = super()._get_motion_times(env_ids)
        if not self._perturb_ready:
            return times
        ids = self._motion_ids if env_ids is None else self._motion_ids[env_ids]
        phase = self._feedback_phase if env_ids is None else self._feedback_phase[env_ids]
        mask = self._perturbed_rows & ~self._recovery_rows
        if env_ids is not None:
            mask = mask[env_ids]
        fraction = torch.atan2(phase[:, 1], phase[:, 0])/(2*math.pi)
        predicted = torch.remainder(fraction-self._phase_offsets[ids], 1.)*self._motion_lib.get_motion_length(ids)
        return torch.where(mask, predicted, times)

    def _command_phase(self, env_ids=None, dt=0.):
        ids, phase = super()._command_phase(env_ids, dt)
        if not self._perturb_ready:
            return ids, phase
        mask = self._perturbed_rows if env_ids is None else self._perturbed_rows[env_ids]
        feedback = self._feedback_phase if env_ids is None else self._feedback_phase[env_ids]
        return ids, torch.where(mask[:, None], feedback, phase)

    def next_phase_target(self):
        target = super().next_phase_target()
        if not self._perturb_ready:
            return target
        # Autoregressive rows have no authored or nominal-speed phase target.
        # Return their current feedback for display only; the optimizer masks
        # these labels out entirely, including normal recovery feedback rows.
        return torch.where((self._phase_supervision_mask == 0)[:, None], self._feedback_phase, target)

    def _append_extremity_speed_loss(self, terms, pos, vel, ang):
        weight = float(self._perturb_cfg.get('extremity_speed_loss_weight', 0.))
        if not weight:
            return terms
        ids = self._extremity_speed_ids[1:]
        # Reward already supplies body-origin world velocities, not COM velocities.
        relative = vel[:, ids] - vel[:, :1] - torch.cross(
            ang[:, :1].expand(-1, 4, -1), pos[:, ids] - pos[:, :1], dim=-1)
        excess = (relative.norm(dim=-1) - self._extremity_speed_limits[self._motion_ids]).clamp_min(0.)
        cost = excess.square().mean(-1) * weight
        cost = torch.where(self._perturbed_rows & ~self._recovery_rows, cost, 0.)
        return torch.cat((terms, cost[:, None]), -1)

    def _foot_regularizer_raw(self, rot):
        command = self._engine._controls.target_vel[self._get_char_id()][:, self._foot_command_ids]
        return getup_foot_costs(command, rot[:, self._foot_cost_ids], rot[:, self._foot_calf_ids],
                               self._foot_idle_local[self._motion_ids])

    def _tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):
        terms = self._base_perturbed_tracking_losses(pos, rot, vel, ang, target_vel, target_ang)
        if not self._perturb_ready:
            return terms
        if self._foot_regularizers_enabled:
            costs = self._foot_regularizer_raw(rot) * self._foot_cost_weights
            costs = torch.where(self._perturbed_getup[:, None], costs, 0.)
            terms = torch.cat((terms, costs), -1)
        if self._pelvis_horizontal_enabled:
            # absolute_walk already subtracts omega x COM-offset from engine COM velocity.
            raw = getup_pelvis_horizontal_cost(vel[:, 0], self._pelvis_horizontal_limits[self._recovery_motion])
            cost = torch.where(self._perturbed_getup, raw*self._pelvis_horizontal_weight, 0.)
            terms = torch.cat((terms, cost[:, None]), -1)
        return terms

    def _base_perturbed_tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):
        if self._perturb_ready:
            self._refresh_reward_rotations()
        terms = super()._tracking_losses(pos, rot, vel, ang, target_vel, target_ang)
        if not self._perturb_ready:
            return terms
        ids = self._perturbed_ids
        prior_ids = self._prior_ids
        if len(prior_ids):
            self._prior.append(pos[prior_ids], q.quat_to_matrix(rot[prior_ids]))
            raw = self._prior.cost()
            self._prior_raw[prior_ids] = raw
        mix = (torch.ones_like(self._time_buf) if self._mse_only else
               tracking_blend(torch.round(self._time_buf*30), self._perturb_cfg['ae_ticks'], self._perturb_cfg['blend_ticks']))
        mix = torch.where(self._perturbed_getup, float(self._idle_position_getup), mix)
        self._tracking_mix.copy_(torch.where(self._perturbed_rows, mix, 1.))
        # Extra early MSE shares AE's fade; the ordinary MSE handoff is unchanged.
        mse_mix = self._tracking_mix
        early_weight = float(self._perturb_cfg.get('ae_mse_weight', 0.))
        if early_weight:
            mse_mix = mse_mix + early_weight * (1 - self._tracking_mix)
        pelvis_scale = float(self._perturb_cfg.get('all_rows_pelvis_velocity_mse_multiplier', 1.))
        if pelvis_scale != 1.:
            # Keep the existing body/component mean and handoff weighting.
            pelvis_error = (vel[:, 0] - target_vel[:, 0]).square().mean(-1)
            terms[:, 1] += (pelvis_scale - 1.) * self._loss_weights[1] * pelvis_error / vel.shape[1]
        terms[:, :4] *= mse_mix[:, None]
        idle_pose_scale = float(self._perturb_cfg.get('idle_pose_mse_multiplier', 1.))
        if idle_pose_scale != 1.:
            idle_rows = self._perturbed_rows & ~self._recovery_rows & (self._gaits[self._motion_ids] == -1)
            scale = torch.where(idle_rows, idle_pose_scale, 1.)
            terms[:, 0] *= scale
            terms[:, 2] *= scale
        if 'pelvis_velocity_extra' in self.loss_term_names:
            terms[:, self.loss_term_names.index('pelvis_velocity_extra')] *= mse_mix
        if 'flat_com_velocity' in self.loss_term_names:
            terms[ids, self.loss_term_names.index('flat_com_velocity')] = 0.
        terms[self._perturbed_getup] = 0.
        if self._idle_position_getup:
            # Pure body-origin position MSE, without velocity/rotation/COM/prior
            # terms or deadbands. XY follows pelvis; standing world Z stays fixed.
            rows = self._perturbed_getup
            terms[rows, 0] = (pos[rows]-self.reward_target_pos[rows]).square().mean((1, 2)) * self._getup_position_weight
        ae = self._prior_raw*self._ae_weight*(1-self._tracking_mix)
        if self._perturb_cfg.get('getup_ae_regularizer', False):
            ae = torch.where(self._perturbed_getup, self._prior_raw*self._ae_weight, ae)
        if self._mode == EnvMode.TRAIN and len(prior_ids):
            self._ae_diagnostics[0].add_(raw.sum())
            self._ae_diagnostics[1].add_(len(prior_ids))
        if self._additive_head_reward or self._idle_position_getup:
            return self._append_extremity_speed_loss(torch.cat((terms, ae[:, None]), -1), pos, vel, ang)
        head_loss = getup_head_height_loss(pos[:, self._head_id, 2], self._idle_head_height[self._motion_ids],
            torch.round(self._time_buf*30), self._perturbed_getup)
        head_loss *= self.loss_weights['getup_head_height']
        return self._append_extremity_speed_loss(torch.cat((terms, ae[:, None], head_loss[:, None]), -1), pos, vel, ang)

    def _update_reward(self):
        super()._update_reward()
        if self._perturb_ready and self._idle_position_getup and self._getup_reward_form == 'linear_cost':
            rows = self._perturbed_getup
            self._reward_buf[rows] = 1. - self.loss_terms[rows, 0]
            if self._perturb_cfg.get('getup_ae_regularizer', False):
                self._reward_buf[rows] -= self.loss_terms[rows, self.loss_term_names.index('motion_prior')]
            if self._foot_regularizers_enabled:
                for term in ('feet_target_velocity', 'feet_idle_local_rotation'):
                    self._reward_buf[rows] -= self.loss_terms[rows, self.loss_term_names.index(term)]
            if self._pelvis_horizontal_enabled:
                self._reward_buf[rows] -= self.loss_terms[rows, self.loss_term_names.index('pelvis_horizontal_speed_excess')]
        if not self._perturb_ready or not self._additive_head_reward:
            return
        self._head_height_reward.copy_(getup_head_height_reward(
            self._engine.get_body_pos(self._get_char_id())[:, self._head_id, 2],
            self._idle_head_height[self._motion_ids], torch.round(self._time_buf*30), self._perturbed_getup))
        self._reward_buf.add_(self._head_height_reward)
        if self._mode == EnvMode.TRAIN:
            self._reward_diagnostics[0].add_(self._head_height_reward.sum())
            self._reward_diagnostics[1].add_(self._perturbed_getup.sum())
            self._reward_diagnostics[2].add_(self._reward_buf.sum())
            self._reward_diagnostics[3].add_(self.get_num_envs())

    def take_reward_diagnostics(self):
        head, count, total, all_count = self._reward_diagnostics.cpu().tolist()
        self._reward_diagnostics.zero_()
        return dict(getup_head_height=head/count, total=total/all_count) if count and all_count else {}

    def _extremity_speed_failure(self):
        char = self._get_char_id()
        ids = self._extremity_speed_ids
        pos = self._engine.get_body_pos(char)[:, ids]
        rot = self._engine.get_body_rot(char)[:, ids]
        ang = self._engine.get_body_ang_vel(char)[:, ids]
        vel = self._engine.get_body_vel(char)[:, ids] - torch.cross(
            ang, q.quat_rotate(rot, self._body_com[:, ids]), dim=-1)
        relative = vel[:, 1:] - vel[:, :1] - torch.cross(
            ang[:, :1].expand(-1, 4, -1), pos[:, 1:] - pos[:, :1], dim=-1)
        # Squared norms avoid a square root; rotation does not change length.
        too_fast = (relative.square().sum(-1) > self._extremity_speed_limits_sq[self._motion_ids]).any(-1)
        return too_fast & self._perturbed_rows & ~self._recovery_rows & (self._time_buf > 0)

    def _update_done(self):
        super()._update_done()
        if not self._perturb_ready:
            return
        ticks = torch.round(self._time_buf*30)
        other_ticks = float(self._perturb_cfg.get('episode_ticks', self._episode_length*30))
        ended = ticks >= torch.where(self._perturbed_getup, float(self._perturb_cfg['getup_ticks']), other_ticks)
        # TIME resets bootstrap the observed final state. They are not failures
        # or success terminals with a forced zero value, and add no penalty.
        flags = torch.where(ended, DoneFlags.TIME.value, DoneFlags.NULL.value)
        head_up = self._engine.get_body_pos(self._get_char_id())[:, self._head_id, 2] > self._head_reset_height[self._motion_ids]
        head_reset = self._perturbed_getup & head_up & (ticks > 0)
        if self._success_feet_limit is not None:
            char = self._get_char_id()
            head_rot = self._engine.get_body_rot(char)[:, self._head_id]
            head_ang = self._engine.get_body_ang_vel(char)[:, self._head_id]
            # Engine velocity is at COM; the recorded head height/velocity use its body origin.
            head_offset = q.quat_rotate(head_rot, self._body_com[:, self._head_id])
            head_vel = self._engine.get_body_vel(char)[:, self._head_id] - torch.cross(head_ang, head_offset, dim=-1)
            feet_height = self._engine.get_body_pos(char)[:, self._success_feet_ids, 2]
            head_reset &= getup_success_stability(feet_height, head_vel[:, 2], self._success_feet_limit, self._success_speed_limit)
        success_value = float(self._perturb_cfg.get('getup_success_value', 0.))
        flags = torch.where(head_reset, DoneFlags.SUCC.value if success_value else DoneFlags.TIME.value, flags)
        velocity = com2_velocity(self._engine.get_body_vel(self._get_char_id())[:, self._com2_ids], self._com2_masses)
        failed = com2_failure(velocity, self._com2_targets[self._motion_ids], self._perturb_cfg['min_speed_ratio'])
        failed &= (self._gaits[self._motion_ids] != -1) & (ticks > self._perturb_cfg['grace_ticks'])
        if self._extremity_speed_enabled and self._perturb_cfg.get('extremity_speed_termination', True):
            failed |= self._extremity_speed_failure()
        if self._perturb_cfg.get('getup_low_head_failure_fraction', 0.) > 0:
            failed |= self._perturbed_getup & (ticks >= self._getup_low_head_ticks) & (
                self._engine.get_body_pos(self._get_char_id())[:, self._head_id, 2]
                <= self._idle_head_height[self._motion_ids] * self._perturb_cfg['getup_low_head_failure_fraction'])
        if self._pelvis_ceiling is not None:
            failed |= getup_pelvis_failure(self._perturbed_getup, ticks,
                self._engine.get_body_pos(self._get_char_id())[:, self._pelvis_ceiling_id, 2],
                self._pelvis_ceiling, self._perturb_cfg['getup_failure_pelvis_after_tick'])
        flags = torch.where(failed, DoneFlags.FAIL.value, flags)
        self._done_buf.copy_(torch.where(self._perturbed_rows, flags, self._done_buf).to(self._done_buf.dtype))
        self._reset_reason.copy_(torch.where(self._perturbed_rows,
            torch.where(failed, 1, torch.where(head_reset, 2, torch.where(ended, 3, 0))), 0))
        if success_value:
            # Exactly r + gamma * known-success-value, with zero bootstrap.
            # Scope to head-height success; ordinary clip completion is unchanged.
            bonus = float(self._perturb_cfg['getup_success_discount']) * success_value
            self._reward_buf.add_((head_reset & ~failed).to(self._reward_buf.dtype) * bonus)
        # SimEnv computes reward before done, so apply the terminal cost here,
        # before the rollout collector copies reward into PPO's buffer.
        penalty = float(self._perturb_cfg.get('getup_failure_penalty', 0.))
        if penalty:
            self._reward_buf.sub_((self._perturbed_getup & failed).to(self._reward_buf.dtype) * penalty)
        loco_penalty = float(self._perturb_cfg.get('loco_failure_penalty', 0.))
        if loco_penalty:
            loco_failed = self._perturbed_rows & (self._gaits[self._motion_ids] != -1) & failed
            self._reward_buf.sub_(loco_failed.to(self._reward_buf.dtype) * loco_penalty)
        normal_penalty = float(self._perturb_cfg.get('normal_getup_failure_penalty', 0.))
        if normal_penalty:
            normal_failed = self._recovery_rows & ~self._perturbed_rows & (self._done_buf == DoneFlags.FAIL.value)
            self._reward_buf.sub_(normal_failed.to(self._reward_buf.dtype) * normal_penalty)
        if self._mode == EnvMode.TRAIN:
            # Per-world counters only; reduce/copy to CPU at the logging cadence.
            self._outcome_ends.add_(self._done_buf != DoneFlags.NULL.value)
            self._outcome_failures.add_(self._done_buf == DoneFlags.FAIL.value)
            self._outcome_head_resets.add_(head_reset & ~failed)

    def take_training_outcomes(self):
        loco = self._perturbed_rows & (self._gaits[self._motion_ids] != -1)
        getup = self._perturbed_getup
        normal_getup = self._recovery_rows & ~self._perturbed_rows
        values = torch.stack((
            self._outcome_failures[loco].sum(), self._outcome_ends[loco].sum(),
            self._outcome_failures[getup].sum(), self._outcome_ends[getup].sum(),
            self._outcome_head_resets[getup].sum(),
            self._outcome_failures[normal_getup].sum(), self._outcome_ends[normal_getup].sum())).cpu().tolist()
        self._outcome_ends.zero_()
        self._outcome_failures.zero_()
        self._outcome_head_resets.zero_()
        return dict(zip(('loco_failures','loco_episodes','getup_failures','getup_episodes','getup_head_resets',
                         'normal_getup_failures','normal_getup_episodes'),values))

    def take_prior_diagnostics(self):
        values = self._ae_diagnostics.cpu().tolist()
        self._ae_diagnostics.zero_()
        return dict(raw_cost=values[0]/values[1]) if values[1] else {}

    def recovery_row_metadata(self, world):
        result = super().recovery_row_metadata(world)
        perturbed = bool(self._perturbed_rows[world])
        if not perturbed:
            result['perturbed_row'] = False
            result['auto_phase_supervised'] = bool(self._phase_supervision_mask[world])
            if bool(self._recovery_rows[world]):
                result['normal_getup_failure_penalty'] = float(self._perturb_cfg.get('normal_getup_failure_penalty', 0.))
            return result
        getup = bool(self._recovery_rows[world])
        loco = bool(self._gaits[self._motion_ids[world]] != -1)
        result.update(perturbed_row=True, auto_phase_feedback=True, target_termination_bodies=[],
            sphere_only=False, timeout_only=not loco, reset_at_getup_end=False,
            perturbation=(('whole-pose vanilla-to-limp blend; authored velocities' if self._limp_dofs is not None
                           else 'local locomotion pose; pelvis unchanged') if getup else 'world-Z yaw, trunk COM velocity preserved'),
            start_yaw_degrees=float(self._yaw_degrees[world]), random_local_pose_frame=int(self._random_pose_frame[world]),
            local_pose_blend=float(self._pose_blend[world]) if getup else None,
            phase_target_mode='prior-tick prediction controls input and MSE target; no phase supervision',
            auto_phase_supervised=False,
            ae_only=False, ae_tracking_only=getup, ae_ticks=self._perturb_cfg['ae_ticks'], blend_ticks=self._perturb_cfg['blend_ticks'],
            head_height_loss_after_tick=60 if getup and not self._additive_head_reward else None,
            head_height_reward_after_tick=60 if getup and self._additive_head_reward else None,
            head_height_loss_target_m=float(self._idle_head_height[self._motion_ids[world]]) if getup else None,
            getup_max_ticks=self._perturb_cfg['getup_ticks'] if getup else None,
            getup_failure_pelvis_height_m=self._pelvis_ceiling if getup else None,
            getup_failure_pelvis_after_tick=self._perturb_cfg.get('getup_failure_pelvis_after_tick') if getup else None,
            head_reset_height_m=float(self._head_reset_height[self._motion_ids[world]]) if getup else None,
            success_max_feet_height_m=self._success_feet_limit if getup else None,
            success_max_head_vertical_speed_m_s=self._success_speed_limit if getup else None,
            success_measurement='world Z at body origins; absolute head vertical speed' if getup and self._success_feet_limit is not None else None,
            com2_termination=loco, com2_target_xy_m_s=self._com2_targets[self._motion_ids[world]].cpu().tolist(),
            com2_grace_ticks=self._perturb_cfg['grace_ticks'], com2_speed_ratios=[self._perturb_cfg['min_speed_ratio'], 1.7])
        if self._extremity_speed_enabled and not getup:
            result.update(timeout_only=not loco and not self._perturb_cfg.get('extremity_speed_termination', True), extremity_speed_bodies=['right_foot','left_foot','right_hand','left_hand'],
                extremity_speed_limits_m_s=self._extremity_speed_limits[self._motion_ids[world]].cpu().tolist(),
                extremity_speed_frame='body origins relative to translating and rotating pelvis', extremity_speed_first_tick=1)
        result['perturbed_plus_row'] = bool(self._perturbed_plus[world])
        if getup:
            result['getup_low_head_failure_tick'] = int(self._getup_low_head_ticks[world])
        if bool(self._perturbed_plus[world]):
            result.update(perturbation='whole-pose vanilla-to-limp blend; independent locomotion linear/joint velocities and random 3D spin',
                initial_linear_velocity_frame=int(self._plus_linear_frame[world]),
                initial_joint_velocity_frame=int(self._plus_joint_frame[world]),
                initial_pelvis_origin_velocity_m_s=self._plus_root_velocity[world].cpu().tolist(),
                initial_root_angular_velocity_rad_s=self._plus_spin[world].cpu().tolist(),
                initial_joint_velocity=self._motion_lib._frame_dof_vel[self._plus_joint_frame[world]].cpu().tolist())
        if loco:
            result['loco_failure_penalty'] = float(self._perturb_cfg.get('loco_failure_penalty', 0.))
        if self._mse_only:
            result.update(ae_only=False, ae_tracking_only=False, ae_disabled=True,
                ae_ticks=0, blend_ticks=0, perturbed_max_ticks=int(self._perturb_cfg.get('episode_ticks',self._episode_length*30)))
        if getup and self._limp_dofs is not None:
            result['limp_pose_index'] = result.pop('random_local_pose_frame')
            result['whole_pose_blend'] = result['local_pose_blend']
            result['limp_dataset_sha256'] = self._perturb_cfg['getup_limp_sha256']
            result['reset_floor_lift_m'] = float(self._reset_floor_lift[world])
            result['reset_floor_clearance_corrected'] = self._limp_floor_support is not None
        if getup and self._idle_position_getup:
            result.update(ae_tracking_only=False, target_position_mode='idle frame 0; pelvis XY following; fixed world height and heading',
                phase_target_mode='autoregressive input; fixed idle frame-0 MSE target',
                head_height_loss_after_tick=None, head_height_reward_after_tick=None,
                position_mse_leeway=None, active_loss_terms=['position_mse'],
                getup_position_mse_weight=self._getup_position_weight,
                getup_position_reward_form=self._getup_reward_form,
                getup_failure_penalty=float(self._perturb_cfg.get('getup_failure_penalty',0.)),
                getup_success_bonus=float(self._perturb_cfg.get('getup_success_value',0.))*float(self._perturb_cfg.get('getup_success_discount',0.)),
                reward_from_loss=self._getup_reward_form,
                reward_definition=('1 - weighted position MSE' if self._getup_reward_form == 'linear_cost'
                                   else '1/(1+weighted position MSE)'),
                pelvis_linear_velocity_multiplier=1., getup_objective='idle_frame0_body_positions')
            if self._perturb_cfg.get('getup_ae_regularizer', False):
                result.update(active_loss_terms=['position_mse', 'motion_prior'], ae_disabled=False,
                    getup_ae_regularizer=True, getup_ae_weight=self._ae_weight,
                    reward_definition='1 - weighted position MSE - weighted AE cost')
            if self._foot_regularizers_enabled:
                result['active_loss_terms'] += ['feet_target_velocity', 'feet_idle_local_rotation']
                result['foot_regularizers'] = dict(self._perturb_cfg['getup_foot_regularizers'])
                result['reward_definition'] += ' - weighted ankle target-velocity cost - weighted ankle idle-local rotation cost'
            if self._pelvis_horizontal_enabled:
                result['active_loss_terms'] += ['pelvis_horizontal_speed_excess']
                result['pelvis_horizontal_speed_limit_m_s'] = float(self._pelvis_horizontal_limits[self._recovery_motion[world]])
                result['reward_definition'] += ' - weighted squared pelvis horizontal speed excess'
        return result

    def replay_loss_metadata(self):
        result = super().replay_loss_metadata()
        result['perturbed_curriculum'] = dict(self._perturb_cfg)
        if self._pelvis_horizontal_enabled:
            result['pelvis_horizontal_regularizer'] = dict(self._perturb_cfg['getup_pelvis_horizontal_regularizer'])
            result['pelvis_horizontal_speed_excess_definition'] = 'weight * max(sqrt(vx^2+vy^2)-max_reference_clip_peak,0)^2; world Z-up pelvis BODY ORIGIN velocity in m/s; perturbed get-ups including plus only'
        if self._foot_regularizers_enabled:
            result['foot_regularizers'] = dict(self._perturb_cfg['getup_foot_regularizers'])
            result['feet_target_velocity_definition'] = 'weight * mean of six squared clamped ankle motor target velocities, rad^2/s^2; perturbed get-ups including plus only'
            result['feet_idle_local_rotation_definition'] = 'weight * mean of two squared shortest foot-relative-calf rotation errors against assigned idle frame0, rad^2; perturbed get-ups including plus only'
        result['all_rows_pelvis_velocity_mse_multiplier'] = float(self._perturb_cfg.get('all_rows_pelvis_velocity_mse_multiplier', 1.))
        result['extremity_speed_termination'] = bool(self._extremity_speed_enabled and self._perturb_cfg.get('extremity_speed_termination', True))
        result['extremity_speed_loss_weight'] = float(self._perturb_cfg.get('extremity_speed_loss_weight', 0.))
        result['extremity_speed_loss_definition'] = 'weight * mean(max(pelvis-relative limb speed - limit, 0)^2); perturbed idle/loco only, no fade'
        result['perturbed_idle_pose_mse_multiplier'] = float(self._perturb_cfg.get('idle_pose_mse_multiplier', 1.))
        result['perturbed_idle_pose_mse_scope'] = 'position and rotation, ordinary perturbed idle only, all episode ticks; applied after early/handoff weighting'
        if self._perturb_cfg.get('ae_mse_weight', 0.):
            result['ae_mse_weight'] = float(self._perturb_cfg['ae_mse_weight'])
            result['tracking_mse_multiplier'] = 'mix + ae_mse_weight * (1 - mix); AE multiplier remains 1 - mix'
            result['objective'] += '; calibrated early MSE alongside AE, fading with AE during the existing handoff'
        if self._mse_only:
            result['objective'] += '; perturbed locomotion/idle: full tracking MSE from tick0, autoregressive phase, AE not loaded'
        if self._idle_position_getup:
            result['objective'] += '; perturbed get-ups: body-position MSE to assigned idle frame0, pelvis XY following, no position deadbands'
            result['perturbed_getup_reward_from_loss'] = self._getup_reward_form
            if self._perturb_cfg.get('getup_ae_regularizer', False):
                result['objective'] += '; additionally frozen three-pose AE regularizer on perturbed get-ups only'
        if self._additive_head_reward:
            result['additive_head_height_reward'] = True
            result['reward_from_loss'] = 'reciprocal_sum_plus_getup_head_height'
            result['reward_definition'] = '1/(1+tracking_cost) + clamp(headZ/idle_frame0_headZ,0,1) only for perturbed get-ups after tick60'
        if self._perturb_cfg.get('getup_success_value',0.):
            result['terminal_meaning'] += '; perturbed get-up head-height reset uses 2 (known success continuation paid once, zero bootstrap)'
        else:
            result['terminal_meaning'] += '; perturbed get-up head-height reset uses 3 (bootstrap, no penalty)'
        loco_penalty = float(self._perturb_cfg.get('loco_failure_penalty', 0.))
        result['terminal_meaning'] += f'; perturbed locomotion COM2 failure uses 1 (terminal reward subtraction {loco_penalty:g})'
        normal_penalty = float(self._perturb_cfg.get('normal_getup_failure_penalty', 0.))
        if normal_penalty:
            result['terminal_meaning'] += f'; normal get-up failure uses 1 (terminal reward subtraction {normal_penalty:g}); normal completion and timeout unchanged'
        if self._perturb_cfg.get('getup_low_head_failure_fraction', 0.) > 0:
            result['getup_low_head_failure_fraction'] = self._perturb_cfg['getup_low_head_failure_fraction']
            result['getup_default_low_head_failure_tick'] = self._perturb_cfg['getup_low_head_failure_tick']
            penalty = float(self._perturb_cfg.get('getup_failure_penalty', 0.))
            tick = self._perturb_cfg['getup_low_head_failure_tick']
            result['terminal_meaning'] += f'; perturbed get-up low head from tick{tick} uses 1 (failure, terminal reward subtraction {penalty:g})'
        return result
