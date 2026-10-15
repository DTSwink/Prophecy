"""Bounded velocity motors in the EXISTING contact/limit solve.

MuJoCo's bounded scalar constraint objective already represents
tau=clip(-D*(J*a-aref),-cap,cap). Set D=h*k, aref=(target-current)/h.
This is the desired implicit capped motor, solved jointly with contacts.
No changes to model gains, caps, inertia, contact parameters, solver iterations.
Only the owned model's existing extension hook is used; restore reverses hooks.
"""
import numpy as np
import warp as wp
from mujoco_warp._src import forward, types

def install_dispatch():
    """One process-local dispatcher; unregistered models remain upstream.

    Model ownership avoids stacked bound-method hooks retaining old environments
    or restoring the wrong hook when two environments close out of order.
    """
    if getattr(forward.implicit, '_uefn_velocity_dispatch', False):
        return
    original_integrate=forward.implicit
    original_actuation=forward.fwd_actuation
    def actuation(m,d):
        motor=getattr(m,'uefn_velocity_motors',None)
        if motor is not None and d is motor.data:
            return motor.actuation(m,d)
        return original_actuation(m,d)
    def integrate(m,d):
        motor=getattr(m,'uefn_velocity_motors',None)
        if motor is not None and d is motor.data:
            return motor.integrate(m,d)
        return original_integrate(m,d)
    integrate._uefn_velocity_dispatch=True
    forward.fwd_actuation=actuation
    forward.implicit=integrate


@wp.struct
class MotorRows:
    nv: int
    count: int
    direct_count: int
    njmax: int
    timestep: wp.array(dtype=float)
    sparse: bool
    dofs: wp.array(dtype=int)
    acts: wp.array(dtype=int)
    direct: wp.array(dtype=int)
    gains: wp.array(dtype=float)
    caps: wp.array(dtype=float)
    ctrl: wp.array2d(dtype=float)
    qvel: wp.array2d(dtype=float)
    nf: wp.array(dtype=int)
    nefc: wp.array(dtype=int)
    rowids: wp.array2d(dtype=int)
    type: wp.array2d(dtype=int)
    id: wp.array2d(dtype=int)
    rownnz: wp.array2d(dtype=int)
    rowadr: wp.array2d(dtype=int)
    colind: wp.array3d(dtype=int)
    J: wp.array3d(dtype=float)
    pos: wp.array2d(dtype=float)
    margin: wp.array2d(dtype=float)
    D: wp.array2d(dtype=float)
    vel: wp.array2d(dtype=float)
    aref: wp.array2d(dtype=float)
    bound: wp.array2d(dtype=float)

@wp.kernel
def add_rows(r: MotorRows):
    w,a=wp.tid()
    dt=r.timestep[0]
    j=r.dofs[a]
    row=wp.atomic_add(r.nefc,w,1)
    wp.atomic_add(r.nf,w,1)
    r.rowids[w,a]=row
    if row>=r.njmax:
        return
    if r.sparse:
        adr=row*r.nv
        r.rownnz[w,row]=1;r.rowadr[w,row]=adr
        r.colind[w,0,adr]=j;r.J[w,0,adr]=1.0
    else:
        for i in range(r.nv):
            r.J[w,row,i]=0.0
        r.J[w,row,j]=1.0
    r.type[w,row]=types.ConstraintType.FRICTION_DOF
    r.id[w,row]=j
    r.pos[w,row]=0.0;r.margin[w,row]=0.0
    r.D[w,row]=dt*r.gains[a]
    r.vel[w,row]=r.qvel[w,j]-r.ctrl[w,r.acts[a]]
    r.aref[w,row]=-r.vel[w,row]/dt
    r.bound[w,row]=r.caps[a]

@wp.kernel
def read_solution(rows: MotorRows, force: wp.array2d(dtype=float), accel: wp.array2d(dtype=float),
                  torque: wp.array2d(dtype=float), stats: wp.array2d(dtype=float), actuator_force: wp.array2d(dtype=float)):
    w=wp.tid()
    dt=rows.timestep[0]
    defect=float(0.0)
    for a in range(rows.count):
        row=rows.rowids[w,a]
        if row>=rows.njmax:
            defect=1e20
        else:
            torque[w,a]=force[w,row]
            actuator_force[w,rows.acts[a]]=force[w,row]
            speed=rows.qvel[w,rows.dofs[a]]+dt*accel[w,rows.dofs[a]]
            expected=wp.clamp(rows.gains[a]*(rows.ctrl[w,rows.acts[a]]-speed),-rows.caps[a],rows.caps[a])
            defect=wp.max(defect,wp.abs(force[w,row]-expected))
    stats[w,0]=defect
    stats[w,1]=float(rows.nefc[w])
    external=float(0.0)
    for a in range(rows.direct_count):
        external=wp.max(external,wp.abs(rows.ctrl[w,rows.direct[a]]))
    stats[w,2]=external

class CoupledVelocityMotors:
    def __init__(self,model,data,cpu_model):
        m = cpu_model
        assert m.ntendon == 0 and np.all(m.dof_damping >= 0)
        assert np.all(m.dof_frictionloss == 0)
        self.nv = m.nv
        ids=[]; dofs=[]; gains=[]; bounds=[];direct=[]
        for a in range(m.nu):
            gain = m.actuator_gainprm[a]
            bias = m.actuator_biasprm[a]
            if np.all(gain == 0) and np.all(bias == 0):
                continue
            if gain[0]==1 and np.all(gain[1:]==0) and np.all(bias==0):
                direct.append(a)
                continue
            assert m.actuator_dyntype[a] == 0 and m.actuator_gaintype[a] == 0
            assert m.actuator_biastype[a] == 1 and gain[0] > 0
            np.testing.assert_allclose(bias[:3], [0, 0, -gain[0]], atol=1e-8)
            assert m.actuator_trntype[a] == 0
            gear = m.actuator_gear[a]
            assert np.count_nonzero(gear) == 1 and np.max(gear) == 1
            joint = m.actuator_trnid[a, 0]
            dof = m.jnt_dofadr[joint] + int(np.argmax(gear[:3]))
            assert m.jnt_type[joint] in (1, 3)
            bound=m.actuator_forcerange[a].copy() if m.actuator_forcelimited[a] else np.array([-np.inf,np.inf])
            if m.jnt_actfrclimited[joint]:
                assert m.jnt_type[joint]==3, 'Non-scalar joint-level force cap needs separate treatment'
                bound[0]=max(bound[0],m.jnt_actfrcrange[joint,0])
                bound[1]=min(bound[1],m.jnt_actfrcrange[joint,1])
            assert np.isfinite(bound).all(), 'Prototype requires an existing finite actuator or scalar joint cap'
            ids.append(a); dofs.append(dof); gains.append(gain[0]); bounds.append(bound)
        assert len(set(dofs)) == len(dofs)
        self.ids = np.array(ids); self.dof_ids = np.array(dofs)
        self.direct_ids=np.array(direct,dtype=int)
        device=data.qvel.device
        arr=lambda v,dtype:wp.array(v,dtype=dtype,device=device)
        self.dofs=arr(dofs,int); self.acts=arr(ids,int);self.gains=arr(gains,float)
        self.lower=arr(np.array(bounds)[:,0],float);self.upper=arr(np.array(bounds)[:,1],float)
        self.torque=wp.zeros((data.nworld,len(ids)),dtype=float,device=device)
        self.stats=wp.zeros((data.nworld,3),dtype=float,device=device)
        self.original=None
        # Passive damping would also need to enter the shared solve, otherwise
        # post-solve implicit damping changes the velocity the motors solved for.
        assert np.all(cpu_model.dof_damping==0), 'Nonzero passive damping is not handled by this prototype'
        np.testing.assert_array_equal(self.lower.numpy(),-self.upper.numpy())
        self.model=model;self.data=data
        self.extension=model.uefn_compound_limits
        self.original_equalities=None;self.original_actuation=None
        r=MotorRows();r.nv=cpu_model.nv;r.njmax=data.njmax;r.timestep=model.opt.timestep
        r.count=len(self.ids);r.direct_count=len(self.direct_ids)
        r.sparse=types.SPARSE_CONSTRAINT_JACOBIAN
        r.dofs=self.dofs;r.acts=self.acts;r.gains=self.gains;r.caps=self.upper
        r.direct=wp.array(self.direct_ids,dtype=int,device=data.qvel.device)
        r.ctrl=data.ctrl;r.qvel=data.qvel;r.nf=data.nf;r.nefc=data.nefc
        r.rowids=wp.zeros((data.nworld,len(self.ids)),dtype=int,device=data.qvel.device)
        for k in ('type','id','J','pos','margin','D','vel','aref'):
            setattr(r,k,getattr(data.efc,k))
        r.rownnz=data.efc.J_rownnz;r.rowadr=data.efc.J_rowadr;r.colind=data.efc.J_colind
        r.bound=data.efc.frictionloss;self.rows=r

    def add_motors(self,m,d):
        self.original_equalities(m,d)
        if not m.opt.disableflags & types.DisableBit.ACTUATION:
            wp.launch(add_rows,dim=(d.nworld,len(self.ids)),inputs=[self.rows],device=d.qvel.device)

    def actuation(self,m,d):
        assert d is self.data
        # These forces are now represented by bounded rows, not applied twice.
        d.qfrc_actuator.zero_();d.actuator_force.zero_()

    def integrate(self,m,d):
        assert d is self.data
        if not m.opt.disableflags & types.DisableBit.ACTUATION:
            wp.launch(read_solution,dim=d.nworld,inputs=[self.rows,d.efc.force,d.qacc,self.torque,self.stats,d.actuator_force],device=d.qvel.device)
        forward._advance(m,d,d.qacc)

    def install(self):
        assert self.original is None
        assert getattr(self.model,'uefn_velocity_motors',None) is None
        install_dispatch()
        self.original=True
        self.original_equalities=self.extension.equalities
        self.extension.equalities=self.add_motors
        self.model.uefn_velocity_motors=self

    def restore(self):
        if self.original is not None:
            self.extension.equalities=self.original_equalities
            self.model.uefn_velocity_motors=None
            self.original=None;self.original_equalities=None;self.original_actuation=None
