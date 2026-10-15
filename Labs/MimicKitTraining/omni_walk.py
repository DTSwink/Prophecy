"""Prepared omni task: current physical state + five command/phase floats.

No future poses, clip identity, speed scalar or predicted-phase feedback.
Reference trajectories remain private reward/reset data. No launcher here.
"""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import torch
from util import torch_util as q
from envs.base_env import DoneFlags
from absolute_walk import AbsoluteWalkEnv
from omni_policy import circular_phase
from uefn_engine import UefnNewtonEngine


def phase_at(times, duration, offset, dt=0.):
    return circular_phase(torch.remainder((times+dt)/duration+offset, 1.))


def append_commands(physical, gait, direction, phase):
    return torch.cat((physical, gait[:, None], direction, phase), -1)


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

    def _build_engine(self, engine_config, num_envs, device, visualize, record_video=False):
        return UefnNewtonEngine(engine_config, num_envs, device, visualize, record_video)

    def _build_sim_tensors(self, config):
        super()._build_sim_tensors(config)
        entries = {r['id']: r for r in self._omni_manifest['motions']}
        rows = [entries[Path(self._motion_lib.get_motion_file(i)).stem]
                for i in range(self._motion_lib.get_num_motions())]
        self._gaits = torch.tensor([r['gait'] for r in rows], device=self._device, dtype=torch.float32)
        self._directions = torch.tensor([r['direction'] for r in rows], device=self._device, dtype=torch.float32)
        self._phase_offsets = torch.tensor([r['phase_offset'] for r in rows], device=self._device, dtype=torch.float32)
        expected = torch.tensor([r['duration'] for r in rows], device=self._device)
        torch.testing.assert_close(self._motion_lib.get_motion_lengths(), expected)
        torch.testing.assert_close(self._directions.norm(dim=-1), torch.ones_like(self._gaits))
        assert torch.all((self._gaits == 0) | (self._gaits == 1))
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

    def _update_done(self):
        super()._update_done()
        ids=self._termination_ids;char=self._get_char_id()
        self.target_distances_sq.copy_(centre_distances(self._engine.get_body_pos(char)[:,ids],
            self._engine.get_body_rot(char)[:,ids],self.reward_target_pos[:,ids],
            self.reward_target_rot[:,ids],self._termination_offsets))
        failed=(self.target_distances_sq>self._target_radius_sq).any(-1)&(self._time_buf>0)
        self._done_buf[failed]=DoneFlags.FAIL.value

    def replay_loss_metadata(self):
        return dict(super().replay_loss_metadata(),target_deviation=dict(radius_m=self.target_radius_m,
            points=self._termination_points,comparison='Euclidean distance of collider centres; strictly greater than radius'),
            terminal_meaning='1=stock contact/pose failure or target deviation; 3=timeout')

    def _command_phase(self, env_ids=None, dt=0.):
        ids = self._motion_ids if env_ids is None else self._motion_ids[env_ids]
        times = self._get_motion_times(env_ids)
        phase = phase_at(times, self._motion_lib.get_motion_length(ids), self._phase_offsets[ids], dt)
        return ids, phase

    def _compute_obs(self, env_ids=None):
        physical = super()._compute_obs(env_ids)
        ids, phase = self._command_phase(env_ids)
        return append_commands(physical, self._gaits[ids], self._directions[ids], phase)

    def next_phase_target(self):
        return self._command_phase(dt=self._engine.get_timestep())[1]
