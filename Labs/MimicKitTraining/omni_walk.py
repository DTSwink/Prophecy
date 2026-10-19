"""Prepared omni task: physical state plus commands and circular phase.

No future poses, clip identity, speed scalar or predicted-phase feedback.
Reference trajectories remain private reward/reset data. No launcher here.
"""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import torch
import warp as wp
import math
from util import torch_util as q
from envs.base_env import DoneFlags, EnvMode
from absolute_walk import AbsoluteWalkEnv
from omni_policy import circular_phase
from uefn_engine import build_uefn_engine
from flat_com import CORE_BODIES, flat_com_velocity, expanded_band, band_loss


def phase_at(times, duration, offset, dt=0.):
    return circular_phase(torch.remainder((times+dt)/duration+offset, 1.))


def append_commands(physical, gait, direction, phase):
    return torch.cat((physical, gait[:, None], direction, phase), -1)


def row_motion_weights(gaits, weights, idle_fraction, worlds):
    """Permanent world membership; reset frequency cannot change idle allocation."""
    assert 0 < idle_fraction <= 1 and worlds > 1
    count = worlds if idle_fraction == 1 else max(1, min(worlds-1, int(worlds*idle_fraction+.5)))
    idle = gaits == -1
    pools = torch.stack((weights*(~idle), weights*idle))
    assert torch.all(pools.sum(-1) > 0)
    return count, pools / pools.sum(-1, keepdim=True)


def fixed_motion_rows(pools, idle_rows, worlds):
    """Allocate the existing motion weights once, rounded to whole agents.

    Stratified allocation keeps each clip within one agent of its quota.
    Stable ordering also preserves assignments across checkpoint resumes.
    """
    rows = []
    for pool, count in ((pools[1], idle_rows), (pools[0], worlds-idle_rows)):
        if count == 0:
            continue
        quantiles = (torch.arange(count, device=pool.device, dtype=pool.dtype)+.5)/count
        rows.append(torch.searchsorted(pool.cumsum(0), quantiles, right=True))
    return torch.cat(rows)


@torch.jit.script
def centre_distances(pos: torch.Tensor, rot: torch.Tensor, target_pos: torch.Tensor,
                     target_rot: torch.Tensor, offsets: torch.Tensor):
    actual=pos+q.quat_rotate(rot,offsets.expand_as(pos))
    target=target_pos+q.quat_rotate(target_rot,offsets.expand_as(pos))
    return (actual-target).square().sum(-1)


class OmniWalkEnv(AbsoluteWalkEnv):
    task_name = 'uefn_omni_absolute_walk'

    def __init__(self, env_config, engine_config, *args, **kwargs):
        config = dict(env_config)
        config.update(enable_tar_obs=False, tar_obs_steps=[], enable_phase_obs=False)
        # Existing absolute walking observations use world axes. Commands use
        # those same fixed axes, not the character's possibly rotated pelvis.
        assert config['global_obs']
        self._omni_manifest = json.loads(Path(config['omni_manifest']).read_text(encoding='utf-8'))
        super().__init__(config, engine_config, *args, **kwargs)
        if 'velocity_command_margin' in config:
            # One-time bounds from the actual loaded motions and motor settings.
            # At reference speed, cap/gain reserves full motor torque authority.
            margin = float(config['velocity_command_margin'])
            if not math.isfinite(margin) or margin < 0:
                raise ValueError('Velocity command margin must be finite and nonnegative')
            motor = self._engine._uefn_motors
            gains = wp.to_torch(motor.gains)
            caps = wp.to_torch(motor.upper)
            if not bool(torch.all(gains > 0)):
                raise ValueError('Velocity command bounds require positive motor gains')
            peaks = self._motion_lib._frame_dof_vel.abs().amax(0)
            bounds = torch.maximum(self._action_bound_high, (peaks + caps / gains) * (1 + margin))
            if not bool(torch.isfinite(bounds).all()):
                raise ValueError('Nonfinite velocity command bounds')
            self._action_bound_high.copy_(bounds)
            self._action_bound_low.copy_(-bounds)
            self._action_space.high[:] = bounds.cpu().numpy()
            self._action_space.low[:] = -bounds.cpu().numpy()
            self.velocity_command_report = dict(margin=margin, reference_peak_rad_s=peaks.cpu().tolist(),
                command_bound_rad_s=bounds.cpu().tolist(), gains=gains.cpu().tolist(),
                torque_caps_nm=caps.cpu().tolist(), existing_limits_never_reduced=True,
                formula='max(old_bound, (reference_peak + torque_cap / gain) * (1 + margin))')

    def _build_engine(self, engine_config, num_envs, device, visualize, record_video=False):
        return build_uefn_engine(engine_config, num_envs, device, visualize, record_video)

    def _build_kin_char_model(self, char_file):
        super()._build_kin_char_model(char_file)
        if str(self._device).startswith('cuda'):
            from fused_kinematics import install
            install(self._kin_char_model)

    def _build_sim_tensors(self, config):
        super()._build_sim_tensors(config)
        entries = {r['id']: r for r in self._omni_manifest['motions']}
        rows = [entries[Path(self._motion_lib.get_motion_file(i)).stem]
                for i in range(self._motion_lib.get_num_motions())]
        self._gaits = torch.tensor([r['gait'] for r in rows], device=self._device, dtype=torch.float32)
        self._equipment_conditioning = bool(config.get('equipment_conditioning', False))
        self._idle_rows = 0
        self._adaptive_rows = None
        if self._equipment_conditioning:
            assert all(type(r.get('sword_drawn')) is bool for r in rows)
            self._equipment = torch.tensor([r['sword_drawn'] for r in rows], device=self._device, dtype=torch.float32)
            # Reserved injury inputs. This experiment explicitly keeps both arms alive.
            self._arm_enabled = torch.ones((self.get_num_envs(),2), device=self._device)
            assert not config.get('arm_injuries_enabled', False), 'Injury sampling is not enabled in this experiment'
            self._idle_rows, pools = row_motion_weights(self._gaits,
                self._motion_lib.get_motion_weights(), float(config['idle_row_fraction']), self.get_num_envs())
            self._fixed_motion_ids = fixed_motion_rows(pools, self._idle_rows, self.get_num_envs())
            if config.get('adaptive_motion_rows'):
                from adaptive_rows import AdaptiveRows
                cfg = config['adaptive_motion_rows']
                self._adaptive_rows = AdaptiveRows(self._fixed_motion_ids, pools, self._idle_rows,
                    seconds=float(cfg['interval_seconds']), max_weight=float(cfg['max_failure_weight']))
        self._directions = torch.tensor([r['direction'] for r in rows], device=self._device, dtype=torch.float32)
        self._phase_offsets = torch.tensor([r['phase_offset'] for r in rows], device=self._device, dtype=torch.float32)
        expected = torch.tensor([r['duration'] for r in rows], device=self._device)
        torch.testing.assert_close(self._motion_lib.get_motion_lengths(), expected)
        torch.testing.assert_close(self._directions.norm(dim=-1), torch.ones_like(self._gaits))
        assert torch.all((self._gaits == -1) | (self._gaits == 0) | (self._gaits == 1))
        idle=self._gaits==-1
        if torch.any(idle):
            torch.testing.assert_close(self._directions[idle],
                torch.tensor([1.,0.],device=self._device).expand(int(idle.sum()),2))
        self.target_radius_m=float(config.get('target_radius_m',.27))
        assert self.target_radius_m>0
        self._target_radius_sq=torch.tensor(self.target_radius_m,device=self._device).square()
        names=['head','right_hand','left_hand','right_foot','left_foot']
        geoms=['head_shape0','hand_r_shape0','hand_l_shape0','foot_r_shape0','foot_l_shape0']
        xml=ET.parse(config['char_file'])
        offsets=[]
        for name,geom in zip(names,geoms):
            node=xml.find(f".//body[@name='{name}']/geom[@name='{geom}']")
            assert node is not None,(name,geom)
            offsets.append([float(v) for v in node.attrib.get('pos','0 0 0').split()])
        self._termination_points=[dict(body=n,offset=p) for n,p in zip(names,offsets)]
        self._termination_ids=torch.tensor([self._kin_char_model.get_body_names().index(n) for n in names],device=self._device)
        self._termination_offsets=torch.tensor(offsets,device=self._device)
        self.target_distances_sq=torch.zeros((self.get_num_envs(),5),device=self._device)
        self._flat_com_config = config.get('flat_com_velocity_loss')
        if self._flat_com_config:
            self._build_flat_com_bands()

    @torch.no_grad()
    def _build_flat_com_bands(self):
        cfg = self._flat_com_config
        self._flat_com_weight = float(cfg['weight'])
        assert math.isfinite(self._flat_com_weight) and self._flat_com_weight > 0
        assert 0 <= cfg['leeway'] <= 1
        names = self._kin_char_model.get_body_names()
        self._flat_com_ids = torch.tensor([names.index(n) for n in CORE_BODIES], device=self._device)
        masses = wp.to_torch(self._engine._sim_model.body_mass).view(self.get_num_envs(), -1)[0, self._flat_com_ids]
        assert torch.all(masses > 0)
        self._flat_com_masses = masses / masses.sum()
        bands = []
        # One-time sampling, at physics resolution, of the same reference and
        # velocity interpolation used by the reward. Never read physics back
        # to the CPU during a training tick.
        for i in range(self._motion_lib.get_num_motions()):
            duration = float(self._motion_lib.get_motion_length(i))
            times = torch.arange(math.ceil(duration*240), device=self._device) / 240
            times = times[times < duration]
            ids = torch.full_like(times, i, dtype=torch.long)
            root, rotation, velocity, angular, joints, dof = self._motion_lib.calc_motion_frame(ids, times)
            pos, rot = self._kin_char_model.forward_kinematics(root, rotation, joints)
            vel, ang = self._world_reference_velocities(pos, rot, velocity, angular, dof, ids, times)
            com_vel = vel + torch.cross(ang, q.quat_rotate(rot, self._body_com[:1].expand_as(pos)), dim=-1)
            reference = flat_com_velocity(com_vel[:, self._flat_com_ids], self._flat_com_masses)
            bands.append(expanded_band(reference, float(cfg['leeway'])))
        self._flat_com_bands = torch.stack(bands)
        assert torch.isfinite(self._flat_com_bands).all()
        self.loss_term_names = (*self.loss_term_names, 'flat_com_velocity')
        self.loss_weights['flat_com_velocity'] = self._flat_com_weight
        self.loss_terms = torch.zeros((self.get_num_envs(), len(self.loss_term_names)), device=self._device)
        self._completed_loss_totals = torch.zeros(len(self.loss_term_names)+1, device=self._device)

    def _tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):
        terms = super()._tracking_losses(pos, rot, vel, ang, target_vel, target_ang)
        if not self._flat_com_config:
            return terms
        velocity = flat_com_velocity(self._engine.get_body_vel(self._get_char_id())[:, self._flat_com_ids], self._flat_com_masses)
        extra = band_loss(velocity, self._flat_com_bands[self._motion_ids]) * self._flat_com_weight
        return torch.cat((terms, extra[:, None]), -1)

    def _position_leeway_rows(self):
        # Recovery rows retain the idle command/motion assignment while their
        # authored get-up target is active. Walk=0 and run=1 use the separate
        # locomotion radius (zero reproduces their original position MSE).
        return self._gaits[self._motion_ids] == -1

    def _reset_envs(self, env_ids):
        if self._adaptive_rows is not None:
            self._adaptive_rows.record_reset(env_ids, self._motion_ids, self._done_buf,
                                             self._mode == EnvMode.TRAIN)
        super()._reset_envs(env_ids)
        refresh = getattr(self._engine, 'refresh_body_velocities', None)
        if refresh is not None:
            # Reset assigns body poses and joint velocities directly. Correct
            # their reported body velocities before any observation/recorder.
            refresh()

    def _reset_ref_motion(self, env_ids):
        if not self._idle_rows:
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

    def _update_done(self):
        super()._update_done()
        ids=self._termination_ids;char=self._get_char_id()
        self.target_distances_sq.copy_(centre_distances(self._engine.get_body_pos(char)[:,ids],
            self._engine.get_body_rot(char)[:,ids],self.reward_target_pos[:,ids],
            self.reward_target_rot[:,ids],self._termination_offsets))
        failed=(self.target_distances_sq>self._target_radius_sq).any(-1)&(self._time_buf>0)
        self._done_buf[failed]=DoneFlags.FAIL.value

    def replay_loss_metadata(self):
        result = dict(super().replay_loss_metadata(),target_deviation=dict(radius_m=self.target_radius_m,
            points=self._termination_points,comparison='Euclidean distance of collider centres; strictly greater than radius'),
            terminal_meaning='1=stock contact/pose failure or target deviation; 3=timeout')
        if self._flat_com_config:
            result['objective'] += '; plus horizontal arm-excluded COM velocity band loss'
            result['flat_com_velocity'] = dict(self._flat_com_config, bodies=list(CORE_BODIES),
                bounds_m_s=self._flat_com_bands.cpu().tolist(), axes='fixed world XY; Z vertical',
                padding='10% of each clip axis range at each end',
                aggregation='mass-weighted COM velocity; mean squared distance outside X/Y bounds')
        return result

    def _command_phase(self, env_ids=None, dt=0.):
        ids = self._motion_ids if env_ids is None else self._motion_ids[env_ids]
        times = self._get_motion_times(env_ids)
        phase = phase_at(times, self._motion_lib.get_motion_length(ids), self._phase_offsets[ids], dt)
        return ids, phase

    def _compute_obs(self, env_ids=None):
        physical = super()._compute_obs(env_ids)
        ids, phase = self._command_phase(env_ids)
        if getattr(self, '_equipment_conditioning', False):
            arms = self._arm_enabled if env_ids is None else self._arm_enabled[env_ids]
            return torch.cat((physical, self._gaits[ids,None], self._directions[ids],
                              self._equipment[ids,None], arms, phase), -1)
        return append_commands(physical, self._gaits[ids], self._directions[ids], phase)

    def next_phase_target(self):
        return self._command_phase(dt=self._engine.get_timestep())[1]
