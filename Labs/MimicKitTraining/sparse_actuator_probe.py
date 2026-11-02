"""Experimental exact structural sparsity for single-axis joint transmissions.

Only redirects the two matching kernels while capturing a disposable engine.
No installed library or production source is changed.
"""
from contextlib import contextmanager
import numpy as np
import warp as wp
import mujoco
from mujoco_warp._src import forward,derivative

@wp.kernel(enable_backward=False)
def actuator_velocity_sparse(qvel:wp.array2d(dtype=float),moment:wp.array3d(dtype=float),
                             dofs:wp.array(dtype=int),out:wp.array2d(dtype=float)):
    w,a=wp.tid()
    k=dofs[a]
    out[w,a]=moment[w,a,k]*qvel[w,k]

@wp.kernel(enable_backward=False)
def derivative_sparse(moment:wp.array3d(dtype=float),vel:wp.array2d(dtype=float),
                      qi:wp.array(dtype=int),qj:wp.array(dtype=int),
                      offsets:wp.array(dtype=int),actuators:wp.array(dtype=int),
                      out:wp.array3d(dtype=float)):
    w,k=wp.tid()
    i=qi[k];j=qj[k];value=float(0.0)
    for at in range(offsets[k],offsets[k+1]):
        a=actuators[at];v=vel[w,a]
        if v!=0.0:
            value+=moment[w,a,i]*moment[w,a,j]*v
    out[w,0,k]=value

class SparseActuators:
    def __init__(self,mjm,m,d):
        assert np.all(mjm.actuator_trntype==mujoco.mjtTrn.mjTRN_JOINT)
        mapping=[]
        for a in range(mjm.nu):
            joint=mjm.actuator_trnid[a,0];kind=mjm.jnt_type[joint]
            assert kind in [mujoco.mjtJoint.mjJNT_BALL,mujoco.mjtJoint.mjJNT_HINGE,mujoco.mjtJoint.mjJNT_SLIDE]
            width=3 if kind==mujoco.mjtJoint.mjJNT_BALL else 1
            nz=np.flatnonzero(mjm.actuator_gear[a,:width])
            assert len(nz)==1 and np.isfinite(mjm.actuator_gear[a]).all()
            mapping.append(int(mjm.jnt_dofadr[joint]+nz[0]))
        self.dofs=wp.array(np.array(mapping,np.int32),device=d.qvel.device)
        qi=m.qM_fullm_i.numpy();qj=m.qM_fullm_j.numpy();offsets=[0];acts=[]
        for i,j in zip(qi,qj):
            acts.extend(a for a,k in enumerate(mapping) if k==i and k==j)
            offsets.append(len(acts))
        self.offsets=wp.array(np.array(offsets,np.int32),device=d.qvel.device)
        self.acts=wp.array(np.array(acts,np.int32),device=d.qvel.device)
        self.m=m;self.d=d;self.mapping=mapping
        self.old_velocity=forward._actuator_velocity(m.nv)
        self.old_derivative=derivative._qderiv_actuator_passive_actuation_sparse
        self.hits={'velocity':0,'derivative':0}
    def velocity(self,out):
        wp.launch(actuator_velocity_sparse,dim=(self.d.nworld,self.m.nu),
                  inputs=[self.d.qvel,self.d.actuator_moment,self.dofs],outputs=[out])
    def deriv(self,vel,out):
        wp.launch(derivative_sparse,dim=(self.d.nworld,self.m.qM_fullm_i.size),
                  inputs=[self.d.actuator_moment,vel,self.m.qM_fullm_i,self.m.qM_fullm_j,self.offsets,self.acts],outputs=[out])
    @contextmanager
    def capture(self):
        launch,tiled=wp.launch,wp.launch_tiled
        def fast_launch(kernel,*args,**kw):
            inputs=kw.get('inputs',[])
            if kernel is self.old_derivative and len(inputs)==5 and inputs[1] is self.d.actuator_moment:
                self.hits['derivative']+=1
                return launch(derivative_sparse,dim=(self.d.nworld,self.m.qM_fullm_i.size),
                    inputs=[inputs[1],inputs[2],inputs[3],inputs[4],self.offsets,self.acts],outputs=kw['outputs'])
            return launch(kernel,*args,**kw)
        def fast_tiled(kernel,*args,**kw):
            inputs=kw.get('inputs',[])
            if kernel is self.old_velocity and len(inputs)==2 and inputs[0] is self.d.qvel and inputs[1] is self.d.actuator_moment:
                self.hits['velocity']+=1
                return launch(actuator_velocity_sparse,dim=(self.d.nworld,self.m.nu),
                    inputs=[inputs[0],inputs[1],self.dofs],outputs=kw['outputs'])
            return tiled(kernel,*args,**kw)
        try:
            wp.launch=fast_launch;wp.launch_tiled=fast_tiled
            yield self
        finally:wp.launch=launch;wp.launch_tiled=tiled
