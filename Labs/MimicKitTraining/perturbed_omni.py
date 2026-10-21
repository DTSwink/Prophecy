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
        torch.testing.assert_close(masses, torch.tensor(table['masses_kg'], device=self._device))
        if not torch.isfinite(self._com2_targets).all():
            raise ValueError('Invalid precomputed COM2 target')
        ids = torch.arange(self._motion_lib.get_num_motions(), device=self._device)
        root, rot, _, _, joints, _ = self._motion_lib.calc_motion_frame(ids, torch.zeros_like(ids, dtype=torch.float32))
        pos, body_rot = self._kin_char_model.forward_kinematics(root, rot, joints)
        self._idle_frame0_pos = pos.clone()
        self._idle_frame0_rot = body_rot.clone()
        # Keep reward/display orientations separate from the spawn reference.
        self.reward_target_rot = self._ref_body_rot.clone()
        self._head_id = names.index('head')
        self._idle_head_height = pos[:, self._head_id, 2]
        self._head_reset_height = self._idle_head_height * float(cfg['getup_head_reset_fraction'])
        # Uniform frames over every locomotion clip, including both D/S variants.
        starts = self._motion_lib._motion_start_idx
        eligible = []
        for i in torch.where(self._gaits != -1)[0].tolist():
            eligible.append(torch.arange(int(starts[i]), int(starts[i]+self._motion_lib._motion_num_frames[i]), device=self._device))
        self._loco_frame_pool = torch.cat(eligible)
        self._loco_reset_dofs = self._motion_lib.joint_rot_to_dof(self._motion_lib._frame_joint_rot[self._loco_frame_pool])
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

    def _tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):
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
        # Perturbed rows use AE then body MSE, without an extra COM-band loss.
        terms[:, :4] *= self._tracking_mix[:, None]
        if 'pelvis_velocity_extra' in self.loss_term_names:
            terms[:, self.loss_term_names.index('pelvis_velocity_extra')] *= self._tracking_mix
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
            return torch.cat((terms, ae[:, None]), -1)
        head_loss = getup_head_height_loss(pos[:, self._head_id, 2], self._idle_head_height[self._motion_ids],
            torch.round(self._time_buf*30), self._perturbed_getup)
        head_loss *= self.loss_weights['getup_head_height']
        return torch.cat((terms, ae[:, None], head_loss[:, None]), -1)

    def _update_reward(self):
        super()._update_reward()
        if self._perturb_ready and self._idle_position_getup and self._getup_reward_form == 'linear_cost':
            rows = self._perturbed_getup
            self._reward_buf[rows] = 1. - self.loss_terms[rows, 0]
            if self._perturb_cfg.get('getup_ae_regularizer', False):
                self._reward_buf[rows] -= self.loss_terms[rows, self.loss_term_names.index('motion_prior')]
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
        success_value = float(self._perturb_cfg.get('getup_success_value', 0.))
        flags = torch.where(head_reset, DoneFlags.SUCC.value if success_value else DoneFlags.TIME.value, flags)
        velocity = com2_velocity(self._engine.get_body_vel(self._get_char_id())[:, self._com2_ids], self._com2_masses)
        failed = com2_failure(velocity, self._com2_targets[self._motion_ids], self._perturb_cfg['min_speed_ratio'])
        failed &= (self._gaits[self._motion_ids] != -1) & (ticks > self._perturb_cfg['grace_ticks'])
        if self._perturb_cfg.get('getup_low_head_failure_fraction', 0.) > 0:
            failed |= self._perturbed_getup & (ticks >= self._perturb_cfg['getup_low_head_failure_tick']) & (
                self._engine.get_body_pos(self._get_char_id())[:, self._head_id, 2]
                <= self._idle_head_height[self._motion_ids] * self._perturb_cfg['getup_low_head_failure_fraction'])
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
            head_reset_height_m=float(self._head_reset_height[self._motion_ids[world]]) if getup else None,
            com2_termination=loco, com2_target_xy_m_s=self._com2_targets[self._motion_ids[world]].cpu().tolist(),
            com2_grace_ticks=self._perturb_cfg['grace_ticks'], com2_speed_ratios=[self._perturb_cfg['min_speed_ratio'], 1.7])
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
        return result

    def replay_loss_metadata(self):
        result = super().replay_loss_metadata()
        result['perturbed_curriculum'] = dict(self._perturb_cfg)
        if self._mse_only:
            result['objective'] += '; perturbed locomotion/idle: full tracking MSE from tick0, autoregressive phase, AE not loaded'
        if self._idle_position_getup:
            result['objective'] += '; perturbed get-ups: pure body-position MSE to assigned idle frame0, pelvis XY following, no deadbands or other losses'
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
            result['getup_low_head_failure_tick'] = self._perturb_cfg['getup_low_head_failure_tick']
            penalty = float(self._perturb_cfg.get('getup_failure_penalty', 0.))
            tick = self._perturb_cfg['getup_low_head_failure_tick']
            result['terminal_meaning'] += f'; perturbed get-up low head from tick{tick} uses 1 (failure, terminal reward subtraction {penalty:g})'
        return result
