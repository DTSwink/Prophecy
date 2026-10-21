"""Replay unchanged physical-observation tensor math in one CUDA graph.

Input copies read the current engine buffers on every call. Outputs own their
storage, so a later reset cannot overwrite PPO's recorded next observation.
Commands and autoregressive phase still use the environment's normal methods.
"""
import types
import torch
from device_quaternion import physical_observations


class PhysicalObservations:
    def __init__(self, env):
        self.env = env
        self.static = None
        self.graph = None

    def inputs(self):
        e, c = self.env._engine, self.env._get_char_id()
        return (e.get_root_pos(c), e.get_root_rot(c), e.get_root_vel(c),
                e.get_root_ang_vel(c), e.get_dof_pos(c), e.get_dof_vel(c),
                e.get_body_pos(c))

    def calculate(self, values):
        root, rot, vel, ang, dof, dvel, body = values
        env = self.env
        joints = env._kin_char_model.dof_to_rot(dof)
        key = body[:, env._key_body_ids] if env._has_key_bodies() else body.new_zeros(0)
        return physical_observations(root, rot, vel, ang, joints, dvel, key,
                                     env._global_obs, env._root_height_obs)

    @torch.no_grad()
    def __call__(self):
        values = self.inputs()
        if self.graph is None:
            self.static = tuple(v.clone() for v in values)
            stream = torch.cuda.Stream(device=values[0].device)
            stream.wait_stream(torch.cuda.current_stream(values[0].device))
            with torch.cuda.stream(stream):
                # Let TorchScript finish specializing before graph capture.
                for _ in range(4):
                    self.calculate(self.static)
            torch.cuda.current_stream(values[0].device).wait_stream(stream)
            self.graph = torch.cuda.CUDAGraph()
            with torch.cuda.graph(self.graph, stream=stream):
                self.output = self.calculate(self.static)
        for destination, current in zip(self.static, values):
            destination.copy_(current)
        self.graph.replay()
        return self.output.clone()


def install(env):
    if getattr(env, '_graphed_physical_observations', None) is not None:
        return
    if not str(env._device).startswith('cuda'):
        return
    if env._enable_phase_obs or env._enable_tar_obs or not env._equipment_conditioning:
        raise ValueError('Graphed omni observations require physical-only base observations')
    physical = PhysicalObservations(env)
    original = env._compute_obs

    def compute(self, env_ids=None):
        if env_ids is not None and len(env_ids) == 0:
            return original(env_ids)
        base = physical()
        if env_ids is not None:
            base = base[env_ids]
        ids, phase = self._command_phase(env_ids)
        arms = self._arm_enabled if env_ids is None else self._arm_enabled[env_ids]
        return torch.cat((base, self._gaits[ids, None], self._directions[ids],
                          self._equipment[ids, None], arms, phase), -1)

    env._compute_obs = types.MethodType(compute, env)
    env._graphed_physical_observations = physical
    env._reference_compute_obs = original
