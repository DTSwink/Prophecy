"""Best pose reached early, followed by five frames of pose/velocity settling."""
import torch
from envs.char_env import CharEnv
from neutral_pose import NeutralPoseEnv


LOSS_NAMES = ('early_pose', 'tail_mse', 'joint_velocity', 'total')


class TimedNeutralPoseEnv(NeutralPoseEnv):
    def _build_sim_tensors(self, config):
        base = dict(config, episode_length=1.5, best_reward=True)
        self._episode_length = 1.5
        super()._build_sim_tensors(base)
        self.task_name = 'timed_best_pose_tail'
        self._reach_steps = 45
        self._tail_steps = 5
        self._episode_steps = 50
        self._episode_length = self._episode_steps * self._engine.get_timestep()
        self.tail_velocity_weight = float(config.get('tail_velocity_weight', 1.0))
        self.tail_multiplier = float(config.get('tail_multiplier', 1.0))
        self.include_pelvis_velocity = bool(config.get('include_pelvis_velocity', False))
        assert self._engine.get_obj_body_names(self._get_char_id())[0] == 'pelvis'
        n = self.get_num_envs()
        self._initial_mse = torch.zeros(n, device=self._device)
        self._best_tick = torch.zeros(n, device=self._device)
        self.loss_terms = torch.zeros((n, 3), device=self._device)
        self._episode_losses = torch.zeros_like(self.loss_terms)
        self._completed_loss_totals = torch.zeros(4, device=self._device)

    def _reset_envs(self, env_ids):
        super()._reset_envs(env_ids)
        self._initial_mse[env_ids] = self._best_mse[env_ids]
        self._best_tick[env_ids] = 0
        self.loss_terms[env_ids] = 0
        self._episode_losses[env_ids] = 0

    def _compute_obs(self, env_ids=None):
        # Preserve the original 141 inputs and the original 45-frame clock.
        # During the extra tail the existing remaining-time input stays at zero.
        obs = CharEnv._compute_obs(self, env_ids)
        ids = slice(None) if env_ids is None else env_ids
        remaining = (1 - self._timestep_buf[ids] / 45).clamp(0, 1)
        return torch.cat((obs, remaining[:, None]), dim=-1)

    def _update_misc(self):
        CharEnv._update_misc(self)
        self._current_mse = self._pose_mse()
        improved = (self._timestep_buf <= 45) & (self._current_mse < self._best_mse)
        self._best_mse.copy_(torch.where(improved, self._current_mse, self._best_mse))
        self._best_tick.copy_(torch.where(improved, self._timestep_buf, self._best_tick))

    def _update_reward(self):
        ticks = self._timestep_buf
        tail = (ticks > 45) & (ticks <= 50)
        multiplier = 4 - 3 * self._best_tick / 45
        improvement = (self._initial_mse - self._best_mse).clamp_min(0)
        self.loss_terms[:, 0] = torch.where(ticks == 45, -improvement * multiplier, 0.)
        self.loss_terms[:, 1] = torch.where(tail, self.tail_multiplier * self._current_mse / 5, 0.)
        char = self._get_char_id()
        velocity_mse = self._engine.get_dof_vel(char).square().mean(dim=-1)
        if self.include_pelvis_velocity:
            velocity_mse = (velocity_mse
                + self._engine.get_body_vel(char)[:, 0].square().mean(dim=-1)
                + self._engine.get_body_ang_vel(char)[:, 0].square().mean(dim=-1))
        self.loss_terms[:, 2] = torch.where(tail, self.tail_multiplier * self.tail_velocity_weight * velocity_mse / 5, 0.)
        self._reward_buf[:] = -self.loss_terms.sum(dim=-1)
        self._episode_losses.add_(self.loss_terms)
        ended = ticks == 50
        self._completed_loss_totals[:3].add_(torch.where(ended[:, None], self._episode_losses, 0.).sum(dim=0))
        self._completed_loss_totals[3].add_(ended.sum())

    def take_completed_losses(self):
        values = self._completed_loss_totals.cpu().tolist()
        self._completed_loss_totals.zero_()
        if values[3] == 0:
            return None
        means = [v / values[3] for v in values[:3]]
        return dict(zip(LOSS_NAMES, means + [sum(means)]))
