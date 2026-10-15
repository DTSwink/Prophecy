"""Walking imitation in world axes. Only target position follows live pelvis XY."""
from typing import List
import math
import torch
import warp as wp
from envs.deepmimic_env import DeepMimicEnv
from anim.kin_char_model import JointType
from util import torch_util as q


@torch.jit.script
def world_velocities(pos: torch.Tensor, rot: torch.Tensor, root_vel: torch.Tensor,
                     root_ang: torch.Tensor, joint_local_ang: torch.Tensor,
                     parents: List[int]):
    velocity = [root_vel]
    angular = [root_ang]
    relative_world = q.quat_rotate(rot[:, 1:], joint_local_ang)
    for j in range(1, len(parents)):
        p = parents[j]
        velocity.append(velocity[p] + torch.cross(angular[p], pos[:, j] - pos[:, p], dim=-1))
        angular.append(angular[p] + relative_world[:, j-1])
    return torch.stack(velocity, 1), torch.stack(angular, 1)


@torch.jit.script
def aligned_positions(actual: torch.Tensor, reference: torch.Tensor):
    shift = actual[:, :1] - reference[:, :1]
    shift = shift * torch.tensor([1., 1., 0.], device=actual.device)
    return reference + shift


@torch.jit.script
def errors(pos: torch.Tensor, rot: torch.Tensor, vel: torch.Tensor, ang: torch.Tensor,
           target_pos: torch.Tensor, target_rot: torch.Tensor,
           target_vel: torch.Tensor, target_ang: torch.Tensor):
    # Each body counts equally. Pelvis contributes Z only to position error.
    position = (pos-target_pos).square().mean((1, 2))
    linear = (vel-target_vel).square().mean((1, 2))
    rotation = (q.quat_to_matrix(rot)-q.quat_to_matrix(target_rot)).square().mean((1, 2, 3))
    angular = (ang-target_ang).square().mean((1, 2))
    return torch.stack([position, linear, rotation, angular], -1)


class AbsoluteWalkEnv(DeepMimicEnv):
    task_name = 'absolute_walk_mse'
    loss_term_names = ('position_mse', 'linear_velocity_mse', 'rotation_mse', 'angular_velocity_mse')
    loss_weights = dict.fromkeys(loss_term_names, 1.)

    def _build_sim_tensors(self, config):
        super()._build_sim_tensors(config)
        self.loss_weights = dict(config.get('absolute_loss_calibration', {}).get('weights', self.loss_weights))
        assert set(self.loss_weights) == set(self.loss_term_names)
        assert all(math.isfinite(v) and v > 0 for v in self.loss_weights.values())
        self._loss_weights = torch.tensor([self.loss_weights[k] for k in self.loss_term_names], device=self._device)
        model = self._kin_char_model
        n = model.get_num_joints()
        assert model.get_body_name(0) == 'pelvis'
        self._velocity_parents = [int(x) for x in model._parent_indices]
        mapping = torch.zeros((model.get_dof_size(), (n-1)*3), device=self._device)
        for j in range(1, n):
            joint = model.get_joint(j)
            start = joint.dof_idx
            if joint.joint_type == JointType.SPHERICAL:
                mapping[start:start+3, (j-1)*3:j*3] = torch.eye(3, device=self._device)
            elif joint.joint_type == JointType.HINGE:
                mapping[start, (j-1)*3:j*3] = joint.axis
            else:
                assert joint.joint_type == JointType.FIXED
        self._velocity_mapping = mapping
        # Match the actual upstream interpolation, including its constant
        # midpoint branch for very small rotations. Stored DOF velocities do
        # not account for that branch, so blindly using them gives false error.
        lib = self._motion_lib
        rotations = torch.cat([lib._frame_root_rot[:, None], lib._frame_joint_rot], 1)
        dot = (rotations * rotations.roll(-1, 0)).sum(-1).abs()
        self._rotation_moving = ((1-dot.square()).sqrt().abs() >= .001) & (dot < 1)
        # Newton reports COM linear velocities. Compare body-origin velocities
        # to the animation FK origins, not mismatched points on each rigid body.
        com = wp.to_torch(self._engine._sim_model.body_com).view(self.get_num_envs(), -1, 3)
        assert com.shape[1] == n, 'This walking task must contain only the character'
        self._body_com = com
        self.loss_terms = torch.zeros((self.get_num_envs(), 4), device=self._device)
        self._completed_loss_totals = torch.zeros(5, device=self._device)
        self.reward_target_pos = torch.zeros_like(self._ref_body_pos)
        self.reward_target_rot = self._ref_body_rot
        self.reward_target_vel = torch.zeros_like(self._ref_body_pos)
        self.reward_target_ang = torch.zeros_like(self._ref_body_pos)

    def _world_reference_velocities(self, pos, rot, root_vel, root_ang, dof_vel, ids, times):
        frame, _, _ = self._motion_lib._calc_frame_blend(ids, times)
        moving = self._rotation_moving[frame]
        local_ang = (dof_vel @ self._velocity_mapping).view(pos.shape[0], -1, 3)
        return world_velocities(pos, rot, root_vel, root_ang*moving[:, :1],
            local_ang*moving[:, 1:, None], self._velocity_parents)

    def _update_reward(self):
        char = self._get_char_id()
        pos = self._engine.get_body_pos(char)
        rot = self._engine.get_body_rot(char)
        ang = self._engine.get_body_ang_vel(char)
        vel = self._engine.get_body_vel(char) - torch.cross(ang, q.quat_rotate(rot, self._body_com), dim=-1)
        target_vel, target_ang = self._world_reference_velocities(self._ref_body_pos, self._ref_body_rot,
            self._ref_root_vel, self._ref_root_ang_vel, self._ref_dof_vel, self._motion_ids, self._get_motion_times())
        self.reward_target_pos.copy_(aligned_positions(pos, self._ref_body_pos))
        self.reward_target_vel.copy_(target_vel)
        self.reward_target_ang.copy_(target_ang)
        self.loss_terms.copy_(errors(pos, rot, vel, ang, self.reward_target_pos,
            self.reward_target_rot, target_vel, target_ang) * self._loss_weights)
        self._reward_buf.copy_(torch.exp(-self.loss_terms.sum(-1)))
        self._completed_loss_totals[:4].add_(self.loss_terms.sum(0))
        self._completed_loss_totals[4].add_(self.get_num_envs())

    def _reset_envs(self, ids):
        super()._reset_envs(ids)
        self.loss_terms[ids] = 0
        pos = self._engine.get_body_pos(self._get_char_id())
        self.reward_target_pos[ids] = aligned_positions(pos[ids], self._ref_body_pos[ids])

    def take_completed_losses(self):
        values = self._completed_loss_totals.cpu().tolist()
        self._completed_loss_totals.zero_()
        if not values[-1]:
            return None
        terms = [x/values[-1] for x in values[:4]]
        return dict(zip((*self.loss_term_names, 'total'), [*terms, sum(terms)]))

    def replay_loss_metadata(self):
        return dict(task=self.task_name, loss_term_names=list(self.loss_term_names),
            loss_weights=self.loss_weights, reward_from_loss='exp_negative_sum',
            objective='Four world-body MSEs with fixed recorded scales; target position follows pelvis XY only; original animation heading and height',
            velocity_reference='Original animation world velocities at body origins, not derivative of XY re-anchoring',
            loss_aggregation='Mean per body/component per tick; rotation matrix MSE; SI units',
            terminal_meaning='Stock DeepMimic: 1=failure, 3=timeout')
