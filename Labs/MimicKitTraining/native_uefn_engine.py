"""Native MJWarp physics, with PHAT-centered spherical ball limits.

Only the MuJoCo joint coordinates are rebased. Newton, policy, motion and
reset coordinates remain unchanged. No custom contact/motor/projection hooks.
"""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import mujoco
import mujoco_warp as mjw
import numpy as np
import warp as wp
from scipy.spatial.transform import Rotation as R
from engines.newton_engine import NewtonEngine


@wp.kernel
def convert_ball_coordinates(source: wp.array2d(dtype=float), target: wp.array2d(dtype=float),
                             starts: wp.array(dtype=int), ends: wp.array(dtype=int),
                             ball: wp.array(dtype=int), reference: wp.array(dtype=wp.quat), inverse: int):
    w, j = wp.tid()
    s = starts[j]
    if ball[j] != 0:
        q = wp.quat(source[w, s+1], source[w, s+2], source[w, s+3], source[w, s])
        r = reference[j]
        if inverse != 0:
            r = wp.quat_inverse(r)
        q = r * q
        target[w, s] = q[3]
        target[w, s+1] = q[0]
        target[w, s+2] = q[1]
        target[w, s+3] = q[2]
    else:
        for k in range(s, ends[j]):
            target[w, k] = source[w, k]


def configure_native_model(model, metadata):
    """One-time CPU configuration; returns the exact coordinate change."""
    model.opt.timestep = 1/240
    model.opt.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    model.opt.solver = mujoco.mjtSolver.mjSOL_NEWTON
    model.opt.cone = mujoco.mjtCone.mjCONE_ELLIPTIC
    model.opt.iterations = 100
    model.opt.ls_iterations = 50
    model.opt.tolerance = 1e-8
    model.opt.impratio = 10
    model.dof_armature[:] = 0
    model.geom_condim[:] = 1
    model.geom_priority[:] = 0
    floor = model.geom_bodyid == 0
    model.geom_condim[floor] = 3
    model.geom_priority[floor] = 1
    model.geom_friction[floor] = [1., .005, .0001]
    model.geom_solref[:] = [.0175, 2.]
    references = np.tile([0., 0., 0., 1.], (model.njnt, 1)).astype(np.float32)
    bounds = {}
    for row in metadata['joints']:
        if row['kind'] != 'ball':
            continue
        matches = [i for i in range(1, model.nbody) if model.body(i).name.endswith(row['body'])]
        if len(matches) != 1:
            raise ValueError('Ambiguous native body ' + row['body'])
        body = matches[0]
        joint = model.body_jntadr[body]
        if model.jnt_type[joint] != mujoco.mjtJoint.mjJNT_BALL:
            raise ValueError('Expected ball joint: ' + row['body'])
        center = R.from_quat(np.roll(row['reference_wxyz'], -1))
        rest = R.from_quat(np.roll(model.body_quat[body], -1))
        model.body_quat[body] = np.roll((rest * center.inv()).as_quat(), 1)
        start = model.jnt_qposadr[joint]
        model.qpos0[start:start+4] = row['reference_wxyz']
        radius = max(row['limits_rad'])
        model.jnt_limited[joint] = True
        model.jnt_range[joint] = [0., radius]
        references[joint] = center.as_quat()
        bounds[row['body']] = float(radius)
    return references, bounds


class NativeUefnEngine(NewtonEngine):
    def __init__(self, config, *args, **kwargs):
        if config['sim_freq'] != 240 or config['control_freq'] != 30 or config['control_mode'] != 'vel':
            raise ValueError('Native UEFN profile requires 240 Hz physics / 30 Hz velocity policy')
        self._native_config = dict(config)
        super().__init__(config, *args, **kwargs)

    def _build_solver(self):
        from torque_envelope import apply_torque_envelope
        caps = self._native_config.get('uefn_motor_torque_caps_nm')
        if caps is not None:
            self.torque_envelope_report = apply_torque_envelope(self._sim_model, caps)
        self._sim_model.joint_armature.zero_()
        super()._build_solver()
        solver = self._solver
        m = solver.mj_model
        metadata = json.loads((Path(self._native_config['uefn_asset_directory']) / 'limits.json').read_text())
        references, bounds = configure_native_model(m, metadata)
        solver.mjw_model = mjw.put_model(m)
        solver.mjw_data = mjw.make_data(m, nworld=self.get_num_envs(), nconmax=150, njmax=450)
        data = solver.mjw_data
        # Newton's existing conversion handles COM/root velocities and joint axes.
        # Rebase only ball quaternion values at the boundary to native MuJoCo.
        starts = wp.array(m.jnt_qposadr.astype(np.int32), device=self._device)
        ends = wp.array(np.r_[m.jnt_qposadr[1:], m.nq].astype(np.int32), device=self._device)
        ball = wp.array((m.jnt_type == mujoco.mjtJoint.mjJNT_BALL).astype(np.int32), device=self._device)
        refs = wp.array(references, dtype=wp.quat, device=self._device)
        original_view = copy.copy(data)
        original_view.qpos = wp.empty_like(data.qpos)
        to_native = solver._update_mjc_data
        from_native = solver._update_newton_state

        def update_native(mj_data, model, state=None):
            to_native(mj_data, model, state)
            wp.launch(convert_ball_coordinates, dim=(mj_data.nworld, m.njnt),
                      inputs=[mj_data.qpos, mj_data.qpos, starts, ends, ball, refs, 0], device=self._device)

        def update_newton(model, state, mj_data, state_prev):
            wp.launch(convert_ball_coordinates, dim=(mj_data.nworld, m.njnt),
                      inputs=[mj_data.qpos, original_view.qpos, starts, ends, ball, refs, 1], device=self._device)
            from_native(model, state, original_view, state_prev)

        solver._update_mjc_data = update_native
        solver._update_newton_state = update_newton
        solver._update_mjc_data(data, self._sim_model, self._sim_state.raw_state)
        # Read-only motor description used by the existing command envelope.
        motor_ids = np.flatnonzero(m.actuator_biasprm[:, 2] != 0)
        gains = -m.actuator_biasprm[motor_ids, 2]
        torque = []
        for a in motor_ids:
            joint = m.actuator_trnid[a, 0]
            torque.append(m.actuator_forcerange[a, 1] if m.actuator_forcelimited[a] else m.jnt_actfrcrange[joint, 1])
        self._uefn_motors = SimpleNamespace(gains=wp.array(gains.astype(np.float32), device=self._device),
                                           upper=wp.array(np.asarray(torque, np.float32), device=self._device))
        self.native_profile_report = dict(profile='native_runlr_soft_contact_20261018',
            spherical_limits_rad=bounds, physics_hz=240, policy_hz=30,
            custom_solver=False, original_policy_coordinates=True,
            gains=gains.tolist(), torque_caps_nm=torque)
        path = Path(self._native_config['uefn_asset_directory']) / 'body_velocity.py'
        spec = importlib.util.spec_from_file_location('native_body_velocity', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._body_velocity = module.BodyVelocity(solver)
        self.native_profile_report['body_velocity_coordinates'] = 'child_axes_world_com_v1'

    def refresh_body_velocities(self):
        self._body_velocity.update(self._sim_state.raw_state)

    def _simulate(self):
        super()._simulate()
        # Once per policy tick, inside the existing CUDA graph. Dynamics and
        # all eight native physics substeps remain unchanged.
        self.refresh_body_velocities()
