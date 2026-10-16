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
        self._capture_failures=bool(config.get('transfer_capture_failures',False))
        super().__init__(config,*args,**kwargs)

    def _build_base_solver(self):
        self._solver=newton.solvers.SolverMuJoCo(self._sim_model,
            solver='newton',njmax=450,nconmax=150,impratio=10,
            iterations=100,ls_iterations=50,jacobian='dense')

    def _build_solver(self):
        super()._build_solver()
        s=self._solver
        self.transfer_contact=SequentialContactAdapter(s.mjw_model,s.mjw_data,s.mj_model,
            self._uefn_motors,iterations=100,allow_soft_limits=True,relaxation=.5,
            hard_limit_control=True,block_motors=True,manifolds=True,jolt_limit_axes=True)
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
        advance=s._mujoco_warp_step
        def step():
            advance()
            self.transfer_projection.apply(self.transfer_contact.p.inv,shared=True)
        s._mujoco_warp_step=step

    def validate_transfer_solver(self):
        # Invoked at rollout boundaries before PPO. No CPU copies per substep.
        failure=self.transfer_contact.error.numpy()
        if np.any(failure):
            raise FloatingPointError('Transfer solver rejected rollout: '+str(np.flatnonzero(failure).tolist()))
