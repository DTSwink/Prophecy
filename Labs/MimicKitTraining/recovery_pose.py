"""Continuous upright position error from randomized back/front floor starts."""
import math
from pathlib import Path
import torch
from neutral_pose import NeutralPoseEnv
from util import torch_util
from replay import geometry


class RecoveryPoseEnv(NeutralPoseEnv):
    task_name = 'continuous_neutral_pose_mse'

    def _build_sim_tensors(self, config):
        super()._build_sim_tensors(config)
        self._reset_rng = torch.Generator(device=self._device).manual_seed(config['reset_seed'])
        self._pose_noise = math.radians(config['reset_joint_noise_degrees'])
        self._floor_clearance = config['reset_floor_clearance_m']
        lo, hi = self._engine.get_obj_dof_limits(0, self._get_char_id())
        self._reset_low = torch.as_tensor(lo, device=self._device, dtype=torch.float32)
        self._reset_high = torch.as_tensor(hi, device=self._device, dtype=torch.float32)
        self._starts_on_back = torch.zeros(self.get_num_envs(), device=self._device, dtype=torch.bool)
        g = geometry(Path(config['char_file']))
        shapes = g['shapes']
        tensor = lambda x: torch.tensor(x, device=self._device, dtype=torch.float32)
        self._shape_bodies = torch.tensor([g['names'].index(s['bone']) for s in shapes], device=self._device)
        self._shape_centers = tensor([s['position'] for s in shapes])
        self._shape_axes = tensor([s['axes'] for s in shapes])
        self._shape_radii = tensor([s.get('radius', 0.) for s in shapes])
        self._shape_extents = tensor([s['dimensions'] if s['kind']=='box' else [0.,0.,s.get('length',0.)] for s in shapes]) * .5

    def _lowest_geometry(self, body_pos, body_rot):
        q = body_rot[:, self._shape_bodies]
        centers = body_pos[:, self._shape_bodies] + torch_util.quat_rotate(q, self._shape_centers.expand(q.shape[0],-1,-1))
        axes = torch_util.quat_rotate(q[:,:,None,:].expand(-1,-1,3,-1), self._shape_axes.expand(q.shape[0],-1,-1,-1))
        extent = (axes[:,:,:,2].abs() * self._shape_extents).sum(-1) + self._shape_radii
        return (centers[:,:,2] - extent).amin(-1)

    def _reset_char(self, env_ids):
        super()._reset_char(env_ids)
        n = env_ids.numel()
        if not n: return
        char = self._get_char_id()
        # Independent 50% probability; reset RNG is separate from action sampling.
        back = torch.rand(n, device=self._device, generator=self._reset_rng) < .5
        self._starts_on_back[env_ids] = back
        rotation = torch.zeros(n,3,device=self._device)
        rotation[:,1] = torch.where(back,-math.pi/2,math.pi/2)
        rotation = torch_util.exp_map_to_quat(rotation)
        noise = (2*torch.rand((n,self._init_dof_pos.numel()),device=self._device,generator=self._reset_rng)-1)*self._pose_noise
        dofs = (self._init_dof_pos + noise).clamp(self._reset_low,self._reset_high)
        root = self._init_root_pos.expand(n,-1).clone()
        pos,rot = self._kin_char_model.forward_kinematics(root,rotation,self._kin_char_model.dof_to_rot(dofs))
        root[:,2] += self._floor_clearance - self._lowest_geometry(pos,rot)
        self._engine.set_root_pos(env_ids,char,root)
        self._engine.set_root_rot(env_ids,char,rotation)
        self._engine.set_dof_pos(env_ids,char,dofs)

    def _update_reward(self):
        # Episode sum is negative mean MSE, independent of control frequency.
        self._reward_buf[:] = -self._pose_mse() / self._episode_steps
