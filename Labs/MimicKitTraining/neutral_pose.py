"""Reference-free control: full-body position MSE to one upright neutral pose."""
import torch
from envs.char_env import CharEnv
from envs.base_env import DoneFlags
from util import torch_util


def body_position_mse(body_pos, root_pos, root_rot, target):
    # Remove XY drift and heading, retaining absolute height and body tilt.
    offset=root_pos.clone();offset[:,2]=0
    local=body_pos-offset[:,None,:]
    heading=torch_util.calc_heading_quat_inv(root_rot)
    rotation=heading[:,None,:].expand(-1,body_pos.shape[1],-1)
    local=torch_util.quat_rotate(rotation.reshape(-1,4),local.reshape(-1,3)).reshape_as(local)
    return (local-target).square().mean(dim=(-2,-1))


class NeutralPoseEnv(CharEnv):
    task_name='neutral_pose_mse'

    def _build_sim_tensors(self,config):
        self._continuous_reward = config.get('continuous_reward', False)
        self._best_reward = config.get('best_reward', False)
        assert not (self._continuous_reward and self._best_reward)
        if self._continuous_reward:
            self.task_name = 'continuous_neutral_pose_mse'
        if self._best_reward:
            self.task_name = 'best_neutral_pose_mse'
        super()._build_sim_tensors(config)
        pose=torch.tensor(config['neutral_pose'],dtype=torch.float32,device=self._device)[None,:]
        target,_=self._kin_char_model.forward_kinematics(pose[:,:3],torch_util.exp_map_to_quat(pose[:,3:6]),
                                                       self._kin_char_model.dof_to_rot(pose[:,6:]))
        assert list(self._kin_char_model.get_body_names())==list(self._engine.get_obj_body_names(self._get_char_id()))
        self._neutral_positions=target
        self._episode_steps=round(self._episode_length/self._engine.get_timestep())
        assert self._episode_steps==45
        if self._best_reward:
            self._best_mse = torch.zeros(self.get_num_envs(), device=self._device)

    def _reset_envs(self,env_ids):
        super()._reset_envs(env_ids)
        if self._best_reward:
            self._best_mse[env_ids] = self._pose_mse()[env_ids]

    def _update_misc(self):
        super()._update_misc()
        if self._best_reward:
            torch.minimum(self._best_mse, self._pose_mse(), out=self._best_mse)

    def _compute_obs(self,env_ids=None):
        obs=super()._compute_obs(env_ids)
        ids=slice(None) if env_ids is None else env_ids
        remaining=(1-self._timestep_buf[ids]/self._episode_steps).clamp(0,1)
        return torch.cat((obs,remaining[:,None]),dim=-1)

    def _pose_mse(self):
        char=self._get_char_id()
        return body_position_mse(self._engine.get_body_pos(char),self._engine.get_root_pos(char),
                                 self._engine.get_root_rot(char),self._neutral_positions)

    def _update_reward(self):
        if self._best_reward:
            self._reward_buf[:]=torch.where(self._timestep_buf>=self._episode_steps,-self._best_mse,0.)
        elif self._continuous_reward:
            # Sum of rewards is negative mean MSE over the same 45-step episode.
            self._reward_buf[:] = -self._pose_mse() / self._episode_steps
        else:
            self._reward_buf[:]=torch.where(self._timestep_buf>=self._episode_steps,-self._pose_mse(),0.)

    def _update_done(self):
        # SUCC is upstream's zero-bootstrap terminal; it means horizon, not standing.
        self._done_buf[:]=torch.where(self._timestep_buf>=self._episode_steps,DoneFlags.SUCC.value,DoneFlags.NULL.value)
