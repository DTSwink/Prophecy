"""Verified UEFN transfer profile, also used by future omni training.

Hard contact/manifold friction and Jolt angular limits in generalized coordinates.
The remaining finite-step articulation difference is measured, not hidden.
"""
import json
import numpy as np
import newton
from uefn_engine import UefnNewtonEngine
from sequential_contact_adapter import SequentialContactAdapter
from limit_projection_gpu import SplitLimitProjection


class ContactTransferEngine(UefnNewtonEngine):
    def __init__(self,config,*args,**kwargs):
        profile=config.get('transfer_solver_profile','legacy_100_50_20')
        profiles={'legacy_100_50_20':(100,50,20),'bounded_jolt_40_20':(40,0,20)}
        if profile not in profiles:raise ValueError('Unknown custom solver profile: '+str(profile))
        self._contact_iterations,self._seed_iterations,self._projection_iterations=profiles[profile]
        self._bounded_sequential=profile=='bounded_jolt_40_20'
        self.transfer_profile_report=dict(profile=profile,contact_iterations=self._contact_iterations,
            seed_iterations=self._seed_iterations,position_iterations=self._projection_iterations,
            physics_hz=240,policy_hz=30,bounded_sequential=self._bounded_sequential,
            relaxation=1. if self._bounded_sequential else .5)
        self._capture_failures=bool(config.get('transfer_capture_failures',False))
        self._floor_aware_projection=bool(config.get('transfer_floor_aware_projection',False))
        super().__init__(config,*args,**kwargs)

    def _build_base_solver(self):
        self._solver=newton.solvers.SolverMuJoCo(self._sim_model,
            solver='newton',njmax=450,nconmax=150,impratio=10,
            iterations=100,ls_iterations=50,jacobian='dense')

    def _build_solver(self):
        super()._build_solver()
        s=self._solver
        self.transfer_contact=SequentialContactAdapter(s.mjw_model,s.mjw_data,s.mj_model,
            self._uefn_motors,iterations=self._contact_iterations,seed_iterations=self._seed_iterations,
            allow_soft_limits=True,relaxation=1. if self._bounded_sequential else .5,
            hard_limit_control=True,block_motors=not self._bounded_sequential,manifolds=True,jolt_limit_axes=True)
        if self._bounded_sequential:
            from bounded_contact_gpu import make_iteration
            self.transfer_contact.iterate_kernel=make_iteration(self.transfer_contact.p.nv)
        self.transfer_contact.install()
        if self._capture_failures:
            from solver_capture import SolverFailureCapture
            self.failure_capture=SolverFailureCapture(self.transfer_contact,s.mjw_data)
        rows=json.loads((self._uefn_directory/'limits.json').read_text())['joints']
        metadata=[]
        for row in rows:
            matches=[i for i in range(1,s.mj_model.nbody)
                     if s.mj_model.body(i).name.endswith(row['body'])]
            assert len(matches)==1,(row['body'],matches)
            metadata.append((s.mj_model.body_jntadr[matches[0]],row))
        self.transfer_projection=SplitLimitProjection(s.mj_model,s.mjw_data,metadata,self._device)
        self.transfer_floor_guard=None
        if self._floor_aware_projection:
            from floor_projection_guard import FloorProjectionGuard
            self.transfer_floor_guard=FloorProjectionGuard(s.mj_model,s.mjw_data,self._device,parallel=True)
        advance=s._mujoco_warp_step
        def step():
            advance()
            if self.transfer_floor_guard is not None:self.transfer_floor_guard.save_before()
            self.transfer_projection.apply(self.transfer_contact.p.inv,iterations=self._projection_iterations,shared=True)
            if self.transfer_floor_guard is not None:self.transfer_floor_guard.apply()
        s._mujoco_warp_step=step

    def validate_transfer_solver(self):
        # Invoked at rollout boundaries before PPO. No CPU copies per substep.
        failure=self.transfer_contact.error.numpy()
        if np.any(failure):
            worlds=np.flatnonzero(failure)
            raise FloatingPointError('Transfer solver rejected rollout: '+str(dict(zip(worlds.tolist(),failure[worlds].tolist()))))
        geometry=self.transfer_contact.p.manifold.diagnostics.numpy()
        peak=int(geometry[:,0].max());split=bool(geometry[:,1].any())
        previous_peak,previous_split=getattr(self,'_reported_contact_geometry',(4,False))
        geometry_warning=peak>previous_peak or (split and not previous_split)
        geometry_info={}
        if geometry_warning:
            self._reported_contact_geometry=(max(4,peak,previous_peak),split or previous_split)
            geometry_info=dict(maximum_contact_patch_points=peak,
                separate_normal_patches=split,
                contact_geometry_note='All contact points retained; differing normals use separate friction patches. Informative only.')
        if self._bounded_sequential and not getattr(self,'_reported_bounded_accuracy',False):
            self._reported_bounded_accuracy=True
            return dict(reason='Explicit fixed-iteration profile; convergence is approximate',
                profile=self.transfer_profile_report,
                maximum_motor_residual_nm=float(self.transfer_contact.p.stats.numpy().max()),**geometry_info)
        if geometry_warning:
            return dict(reason='Contact geometry diagnostic; training continues without resets or discarded samples',**geometry_info)
        counts=self.transfer_contact.p.roundoff_warnings.numpy()
        convergence=self.transfer_contact.p.convergence_warnings.numpy()
        total=int(counts.sum()+convergence.sum())
        if total>getattr(self,'_reported_solver_warnings',0):
            previous=getattr(self,'_reported_solver_warnings',0)
            self._reported_solver_warnings=total
            metrics=self.transfer_contact.p.convergence_metrics.numpy().max(axis=0)
            return dict(reason='Finite solver approximation; training continues, no reset or sample removal',
                total=total,new=total-previous,roundoff_total=int(counts.sum()),convergence_total=int(convergence.sum()),
                worlds=np.flatnonzero(counts+convergence).tolist(),
                maximum_iteration_delta=max(float(self.transfer_contact.p.roundoff_delta.numpy().max()),float(metrics[0])),
                maximum_motor_residual_nm=float(metrics[1]),maximum_contact_limit_velocity_residual=float(metrics[2]))
