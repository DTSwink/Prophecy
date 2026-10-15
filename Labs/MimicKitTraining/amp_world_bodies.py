"""Static-standing AMP with world body state, aligned only in horizontal XY/yaw."""
import pickle
from pathlib import Path
import numpy as np
import torch
from amp_standing import StandingAMPEnv
from util import torch_util
from util.circular_buffer import CircularBuffer


@torch.jit.script
def world_body_observations(pos, rot, vel, ang_vel):
    # One common frame for the whole history: latest pelvis XY and heading.
    # Preserve absolute height, roll/pitch and motion between history samples.
    origin = pos[:, -1, 0, :].clone()
    origin[:, 2] = 0
    heading = torch_util.calc_heading_quat_inv(rot[:, -1, 0, :])
    heading = heading[:, None, None, :].expand_as(rot)
    aligned_pos = torch_util.quat_rotate(heading, pos-origin[:, None, None, :])
    aligned_rot = torch_util.quat_to_tan_norm(torch_util.quat_mul(heading, rot))
    aligned_vel = torch_util.quat_rotate(heading, vel)
    aligned_ang = torch_util.quat_rotate(heading, ang_vel)
    return torch.cat((aligned_pos, aligned_rot, aligned_vel, aligned_ang), dim=-1).flatten(1)


class WorldBodyStandingAMPEnv(StandingAMPEnv):
    """15 bodies x (3 position + 6 orientation + 3 velocity + 3 angular velocity)."""
    def __init__(self, env_config, *args, **kwargs):
        frames = np.asarray(pickle.loads(Path(env_config['motion_file']).read_bytes())['frames'])
        assert np.array_equal(frames, np.broadcast_to(frames[0], frames.shape)), 'World-body standing reference must be static'
        self._static_disc_demo = None
        super().__init__(env_config, *args, **kwargs)

    def _build_disc_obs_buffers(self):
        char = self._get_char_id()
        self._world_body_history = {}
        for name in ('pos', 'rot', 'vel', 'ang_vel'):
            value = getattr(self._engine, 'get_body_'+name)(char)
            self._world_body_history[name] = CircularBuffer(
                batch_size=self.get_num_envs(), buffer_len=self._num_disc_obs_steps,
                shape=value.shape[1:], dtype=value.dtype, device=self._device)
        shape = self.get_disc_obs_space().shape
        self._disc_obs_buf = torch.zeros((self.get_num_envs(), *shape), device=self._device)

    def _compute_disc_obs_demo(self, motion_ids, motion_times0):
        if self._static_disc_demo is None:
            root, rotation, _, _, joints, _, _ = self._fetch_disc_demo_data(motion_ids[:1], motion_times0[:1])
            pos, rot = self._kin_char_model.forward_kinematics(
                root.flatten(0, 1), rotation.flatten(0, 1), joints.flatten(0, 1))
            pos = pos.reshape(1, self._num_disc_obs_steps, -1, 3)
            rot = rot.reshape(1, self._num_disc_obs_steps, -1, 4)
            self._static_disc_demo = world_body_observations(pos, rot, torch.zeros_like(pos), torch.zeros_like(pos))
        return self._static_disc_demo.expand(len(motion_ids), -1)

    def _update_disc_hist(self):
        char = self._get_char_id()
        for name, history in self._world_body_history.items():
            history.push(getattr(self._engine, 'get_body_'+name)(char))

    def _reset_disc_hist(self, env_ids):
        char = self._get_char_id()
        # Engine body transforms are refreshed after reset; reconstruct the
        # actual reset articulation now, never substitute the standing demo.
        pos, rot = self._kin_char_model.forward_kinematics(
            self._engine.get_root_pos(char)[env_ids],
            self._engine.get_root_rot(char)[env_ids],
            self._kin_char_model.dof_to_rot(self._engine.get_dof_pos(char)[env_ids]))
        # Stock reset clears both floating-root and joint velocities.
        for name, value in dict(pos=pos, rot=rot, vel=torch.zeros_like(pos),
                                ang_vel=torch.zeros_like(pos)).items():
            self._world_body_history[name].fill(env_ids,
                value[:, None].expand(-1, self._num_disc_obs_steps, *value.shape[1:]))

    def _update_disc_obs(self, env_ids=None):
        values = [self._world_body_history[k].get_all() for k in ('pos', 'rot', 'vel', 'ang_vel')]
        if env_ids is not None:
            values = [v[env_ids] for v in values]
        obs = world_body_observations(*values)
        if env_ids is None:
            self._disc_obs_buf[:] = obs
        else:
            self._disc_obs_buf[env_ids] = obs
