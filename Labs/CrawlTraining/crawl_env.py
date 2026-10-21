"""Forward crawl/idle observations; unchanged locomotion MSE and motor pipeline."""
import torch
from omni_walk import OmniWalkEnv
from absolute_walk import AbsoluteWalkEnv


class CrawlEnv(OmniWalkEnv):
    task_name = 'uefn_crawl_idle_mse'

    def _build_sim_tensors(self, config):
        assert config['crawl_task'] and config['idle_row_fraction'] == .04
        assert not config['arm_injuries_enabled']
        assert not config.get('adaptive_motion_rows')
        assert not config['enable_early_termination'] and not config['pose_termination']
        super()._build_sim_tensors(config)
        assert self._motion_lib.get_num_motions() == 2
        assert torch.all(self._motion_lib._motion_loop_modes == 1), 'Crawl and idle must loop without clip-end resets'
        # Reserved right arm, left arm, right leg, left leg status. No injuries.
        self._limb_enabled = torch.ones((self.get_num_envs(), 4), device=self._device)

    def _compute_obs(self, env_ids=None):
        physical = AbsoluteWalkEnv._compute_obs(self, env_ids)
        ids, phase = self._command_phase(env_ids)
        limbs = self._limb_enabled if env_ids is None else self._limb_enabled[env_ids]
        # Idle=-1, crawl=0. No direction, speed or drawn/sheathed command.
        return torch.cat((physical, self._gaits[ids, None], limbs, phase), -1)

    def replay_loss_metadata(self):
        result = super().replay_loss_metadata()
        result.update(task=self.task_name, ae_reward=False,
                      command_inputs=['idle_crawl', 'right_arm', 'left_arm', 'right_leg', 'left_leg', 'phase_cos', 'phase_sin'],
                      injuries_enabled=False,adaptive_sampling=False,
                      terminal_meaning='1=collider-target deviation >27cm only; 3=timeout; both references loop')
        return result
