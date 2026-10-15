"""Exact diagonal specialization for verified one-axis native joint motors.

The generic kernel scans every actuator for every mass-matrix entry. Our
transmission Jacobian is constant one-hot, so J.T @ diag(velocity derivative)
@ J is diagonal. Native saturation/derivative evaluation and integration stay
unchanged. Unregistered models keep the original kernel.
"""
import importlib
import importlib.metadata
from pathlib import Path
import numpy as np
import mujoco
import warp as wp
from mujoco_warp._src import derivative


@wp.kernel
def diagonal(is_sparse:bool,dof_motor:wp.array(dtype=int),vel:wp.array2d(dtype=float),
             qi:wp.array(dtype=int),qj:wp.array(dtype=int),out:wp.array3d(dtype=float)):
    world,entry=wp.tid();i=qi[entry];j=qj[entry];value=float(0.)
    if i==j:
        motor=dof_motor[i]
        if motor>=0:value=vel[world,motor]
    if is_sparse:out[world,0,entry]=value
    else:
        out[world,i,j]=value
        if i!=j:out[world,j,i]=value


def install_hook():
    if importlib.metadata.version('mujoco-warp')!='3.6.0':
        raise RuntimeError('Revalidate native motor specialization on a new Warp version')
    path=Path(derivative.__file__);source=path.read_text(encoding='utf-8')
    if '# Prophecy diagonal motor extension' in source:return
    anchor='''      wp.launch(
        _qderiv_actuator_passive_actuation_sparse,
        dim=(d.nworld, qMi.size),
        inputs=[m.nu, m.is_sparse, d.moment_rownnz, d.moment_rowadr, d.moment_colind, d.actuator_moment, vel, qMi, qMj],
        outputs=[out],
      )'''
    if source.count(anchor)!=1:raise RuntimeError('Unexpected native derivative source; refusing to patch')
    replacement='''      # Prophecy diagonal motor extension: verified one-hot joint transmissions only.
      if getattr(m, "prophecy_motor_derivative", None) is not None:
        m.prophecy_motor_derivative(m, d, vel, out)
      else:
'''+''.join('  '+line+'\n' for line in anchor.splitlines()).rstrip('\n')
    path.write_text(source.replace(anchor,replacement),encoding='utf-8');importlib.reload(derivative)


class DiagonalMotorDerivative:
    def __init__(self,model,warp_model,device='cuda:0'):
        mapping=np.full(model.nv,-1,dtype=np.int32)
        for act in range(model.nu):
            if model.actuator_trntype[act]!=mujoco.mjtTrn.mjTRN_JOINT:
                raise ValueError('Only constant local joint transmissions are supported')
            joint=model.actuator_trnid[act,0]
            if model.jnt_type[joint]!=mujoco.mjtJoint.mjJNT_BALL:raise ValueError('Expected ball motor')
            gear=model.actuator_gear[act];nonzero=np.flatnonzero(gear)
            if len(nonzero)!=1 or nonzero[0]>=3 or gear[nonzero[0]]!=1:
                raise ValueError('Expected exact one-hot angular gear')
            dof=model.jnt_dofadr[joint]+nonzero[0]
            if mapping[dof]!=-1:raise ValueError('Duplicate actuator on DOF')
            mapping[dof]=act
        install_hook()
        self.mapping=wp.array(mapping,dtype=int,device=device)
        warp_model.prophecy_motor_derivative=self

    def __call__(self,m,d,vel,out):
        wp.launch(diagonal,dim=(d.nworld,m.qM_fullm_i.size),
            inputs=[m.is_sparse,self.mapping,vel,m.qM_fullm_i,m.qM_fullm_j],outputs=[out])
