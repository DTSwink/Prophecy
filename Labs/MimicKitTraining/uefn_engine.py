"""Opt-in Newton engine: existing UEFN limits, gyro cancellation and body drag.

Velocity motors use bounded end-step velocity in the shared constraint solve.
Ground, solver settings, gains, caps, body mass and inertia remain inherited.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import numpy as np
import warp as wp
from engines.newton_engine import NewtonEngine


@wp.kernel
def compound_forces(pose:wp.array(dtype=wp.transform), velocity:wp.array(dtype=wp.spatial_vector),
                    inertia:wp.array(dtype=wp.mat33), coefficient:wp.array(dtype=float),
                    first:wp.array(dtype=wp.vec3), second:wp.array(dtype=wp.mat33),
                    force:wp.array(dtype=wp.spatial_vector)):
    b=wp.tid()
    rot=wp.quat_to_matrix(wp.transform_get_rotation(pose[b]))
    v=wp.spatial_top(velocity[b]); w=wp.spatial_bottom(velocity[b])
    s=rot*first[b]
    drag=-coefficient[b]*v-wp.cross(w,s)
    torque=-wp.cross(s,v)-rot*second[b]*wp.transpose(rot)*w
    torque+=wp.cross(w,rot*inertia[b]*wp.transpose(rot)*w)
    # Base _pre_sim_step clears forces and adds any external pushes first.
    # This executes once per physics substep, including CUDA graph capture.
    force[b]+=wp.spatial_vector(drag,torque)


class UefnNewtonEngine(NewtonEngine):
    def __init__(self,config,*args,**kwargs):
        self._uefn_directory=Path(config['uefn_asset_directory']).resolve()
        self._zero_joint_armature=bool(config.get('uefn_zero_joint_armature',False))
        self._bounded_velocity_motors=bool(config.get('uefn_bounded_velocity_motors',True))
        assert config['control_mode']=='vel'
        assert config['sim_freq']==240 and config['control_freq']==30
        super().__init__(config,*args,**kwargs)

    def _build_solver(self):
        if self._zero_joint_armature:
            self._sim_model.joint_armature.zero_()
        super()._build_solver()
        if self._zero_joint_armature:
            assert not np.any(self._solver.mj_model.dof_armature)
            assert not np.any(self._solver.mjw_model.dof_armature.numpy())
        folder=self._uefn_directory
        data=json.loads((folder/'physics.json').read_text())
        assert hashlib.sha256((folder/'humanoid_uefn.xml').read_bytes()).hexdigest()==data['asset_sha256']
        spec=importlib.util.spec_from_file_location('uefn_compound_runtime',folder/'runtime.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self._uefn_limits=module.install_limits(self._solver.mj_model,self._solver.mjw_model)
        spec=importlib.util.spec_from_file_location('uefn_body_velocity',folder/'body_velocity.py')
        velocity_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(velocity_module)
        self._body_velocity=velocity_module.BodyVelocity(self._solver)
        if self._bounded_velocity_motors:
            spec=importlib.util.spec_from_file_location('uefn_velocity_runtime',folder/'velocity_motors.py')
            motor_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(motor_module)
            self._uefn_motors=motor_module.CoupledVelocityMotors(
                self._solver.mjw_model,self._solver.mjw_data,self._solver.mj_model)
            # This engine only exposes velocity control. Newton also allocates
            # direct-torque channels; they are unused and must stay zero.
            assert not np.any(self._controls.control.joint_f.numpy())
            self._uefn_motors.install()
        model=self._sim_model
        assert model.body_count==self.get_num_envs()*15, 'Only the UEFN character may use this engine'
        assert np.allclose(model.gravity.numpy(),[0,0,-9.81],atol=1e-5)
        coefficients=[];first=[];second=[];mass=model.body_mass.numpy();com=model.body_com.numpy();inertia=model.body_inertia.numpy()
        for b,label in enumerate(model.body_label):
            matches=[n for n in data['bodies'] if label==n or label.endswith('/'+n) or label.endswith('_'+n)]
            assert len(matches)==1,(label,matches)
            row=data['bodies'][matches[0]]
            np.testing.assert_allclose(mass[b],row['mass'],rtol=2e-5)
            np.testing.assert_allclose(com[b],row['com'],atol=2e-6)
            np.testing.assert_allclose(inertia[b],row['inertia'],atol=2e-6,rtol=2e-5)
            coefficients.append(row['drag_mass']);first.append(row['drag_first']);second.append(row['drag_second'])
        self._drag_coeff=wp.array(coefficients,dtype=float,device=self._device)
        self._drag_first=wp.array(first,dtype=wp.vec3,device=self._device)
        self._drag_second=wp.array(second,dtype=wp.mat33,device=self._device)
        assert self._solver.mj_model.opt.density==0 and self._solver.mj_model.opt.viscosity==0

    def _pre_sim_step(self,raw_state,control):
        self._body_velocity.update(raw_state)
        super()._pre_sim_step(raw_state,control)
        wp.launch(compound_forces,dim=self._sim_model.body_count,
                  inputs=[raw_state.body_q,raw_state.body_qd,self._sim_model.body_inertia,
                          self._drag_coeff,self._drag_first,self._drag_second,raw_state.body_f],device=self._device)

    def _simulate(self):
        super()._simulate()
        # Included in the same CUDA graph; rewards and telemetry see the actual
        # final body velocities, including the last physics substep.
        self._body_velocity.update(self._sim_state.raw_state)

    def _build_dof_force_tensors(self):
        if self._bounded_velocity_motors:
            # The solver's actual actuator order is validated by the motor
            # adapter; do not assume interleaved position/velocity actuators.
            self._dof_forces=[wp.to_torch(self._uefn_motors.torque)]
        else:
            super()._build_dof_force_tensors()
