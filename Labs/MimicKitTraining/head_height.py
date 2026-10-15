"""Terminal reward: min(independent episode head peak, pelvis peak), in meters."""
import torch
from envs.char_env import CharEnv
from envs.base_env import DoneFlags


class HeadHeightEnv(CharEnv):
    task_name = 'minimum_height_peaks'
    def _build_sim_tensors(self, config):
        super()._build_sim_tensors(config)
        names = list(self._engine.get_obj_body_names(self._get_char_id()))
        self._head_id = names.index('head')
        self._pelvis_id = names.index('pelvis')
        self._peak_height = torch.zeros(self.get_num_envs(), device=self._device)
        self._body_peaks = torch.zeros((self.get_num_envs(), 2), device=self._device)
        self._episode_steps = round(self._episode_length / self._engine.get_timestep())
        assert self._episode_steps == 45

    def _height_score(self):
        pos = self._engine.get_body_pos(self._get_char_id())
        return pos[:, self._head_id, 2] + pos[:, self._pelvis_id, 2]

    def _reset_envs(self, env_ids):
        super()._reset_envs(env_ids)
        self._peak_height[env_ids] = self._height_score()[env_ids]
        self._body_peaks[env_ids] = self._heights()[env_ids]

    def _heights(self):
        return self._engine.get_body_pos(self._get_char_id())[:, [self._head_id, self._pelvis_id], 2]

    def _update_misc(self):
        super()._update_misc()
        torch.maximum(self._peak_height, self._height_score(), out=self._peak_height)
        torch.maximum(self._body_peaks, self._heights(), out=self._body_peaks)

    def _compute_obs(self, env_ids=None):
        obs = super()._compute_obs(env_ids)
        ids = slice(None) if env_ids is None else env_ids
        # Retain the old peak-sum/time inputs to preserve the resumed policy.
        # Append the two independent records required by the new objective.
        remaining = (1 - self._timestep_buf[ids] / self._episode_steps).clamp(0, 1)
        return torch.cat((obs, self._peak_height[ids, None], remaining[:, None], self._body_peaks[ids]), dim=-1)

    def _update_reward(self):
        self._reward_buf[:] = torch.where(self._timestep_buf >= self._episode_steps,
                                          self._body_peaks.amin(dim=-1), 0.0)

    def _update_done(self):
        # A real terminal horizon, not TIME truncation: PPO must not bootstrap
        # another episode's value. SUCC is upstream's zero-terminal-value code;
        # it is NOT a claim that the humanoid recovered.
        self._done_buf[:] = torch.where(self._timestep_buf >= self._episode_steps,
                                       DoneFlags.SUCC.value, DoneFlags.NULL.value)
