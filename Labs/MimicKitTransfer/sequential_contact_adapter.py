"""Contained MJWarp contact-law experiment, NOT a training default.

Dense single-articulation models only; angular limits/equalities must be disabled
for the isolated comparison. Existing motor rows supply actuation. This is a
diagnostic integration of the independently tested GPU equations, not a complete
Jolt replacement: manifold friction and position projection are still outstanding.
"""
import numpy as np
import warp as wp
from mujoco_warp._src import solver, types
from sequential_contact_gpu import ContactProblem, prepare_response, prepare_diagonal, make_tiled_iteration


@wp.kernel(enable_backward=False)
def initialize(p: ContactProblem, qvel: wp.array2d(dtype=float), smooth: wp.array2d(dtype=float),
               ctrl: wp.array2d(dtype=float), acts: wp.array(dtype=int)):
    w,j=wp.tid()
    p.free[w,j]=qvel[w,j]+p.dt[0]*smooth[w,j]
    if j<p.nmotor: p.commands[w,j]=ctrl[w,acts[j]]


def make_inverse(nv):
    @wp.kernel(module='unique',enable_backward=False)
    def inverse(L: wp.array3d(dtype=float), identity: wp.array2d(dtype=float), output: wp.array3d(dtype=float)):
        w=wp.tid()
        l=wp.tile_load(L[w],shape=(nv,nv))
        eye=wp.tile_load(identity,shape=(nv,nv))
        inv=wp.tile_cholesky_solve(l,eye)
        wp.tile_store(output[w],inv)
    return inverse


@wp.kernel(enable_backward=False)
def contacts(p: ContactProblem, capacity: int, sparse: bool, nacon: wp.array(dtype=int),
             worldid: wp.array(dtype=int), dim: wp.array(dtype=int), kind: wp.array(dtype=int),
             rows: wp.array2d(dtype=int), efcJ: wp.array3d(dtype=float),
             nnz: wp.array2d(dtype=int), adr: wp.array2d(dtype=int), cols: wp.array3d(dtype=int),
             friction: wp.array(dtype=types.vec5), rowmap: wp.array3d(dtype=int), error: wp.array(dtype=int)):
    c=wp.tid()
    if c>=nacon[0] or not (kind[c]&int(types.ContactType.CONSTRAINT)): return
    if rows[c,0]<0: return
    w=worldid[c]
    slot=wp.atomic_add(p.ncontact,w,1)
    if slot>=capacity or dim[c]!=3:
        error[w]=1
        return
    p.friction[w]=friction[c][0]
    for a in range(3):
        row=rows[c,a]; rowmap[w,slot,a]=row
        if row<0:
            error[w]=2
        elif sparse:
            start=adr[w,row]
            for i in range(nnz[w,row]): p.J[w,slot,a,cols[w,0,start+i]]=efcJ[w,0,start+i]
        else:
            for j in range(p.nv): p.J[w,slot,a,j]=efcJ[w,row,j]


@wp.kernel(enable_backward=False)
def bound_counts(p: ContactProblem, capacity: int):
    w=wp.tid()
    p.ncontact[w]=wp.min(p.ncontact[w],capacity)


@wp.kernel(enable_backward=False)
def finish(p: ContactProblem, qvel: wp.array2d(dtype=float), qacc: wp.array2d(dtype=float),
           mass: wp.array3d(dtype=float), constraint_force: wp.array2d(dtype=float),
           rowforce: wp.array2d(dtype=float), motorrows: wp.array2d(dtype=int),
           contactrows: wp.array3d(dtype=int), error: wp.array(dtype=int)):
    w,j=wp.tid(); dt=p.dt[0]
    qacc[w,j]=(p.velocity[w,j]-qvel[w,j])/dt
    force=float(0.)
    for i in range(p.nv): force+=mass[w,j,i]*(p.velocity[w,i]-p.free[w,i])/dt
    constraint_force[w,j]=force
    if j<p.nmotor: rowforce[w,motorrows[w,j]]=p.motor_impulse[w,j]/dt
    if j==0:
        for c in range(wp.min(p.ncontact[w],p.contact_impulse.shape[1])):
            for a in range(3):
                row=contactrows[w,c,a]
                if row>=0: rowforce[w,row]=p.contact_impulse[w,c,a]/dt
    # A diagnostic caller must check error before accepting any output. Do not
    # silently truncate contacts or pretend unsupported constraint types worked.


class SequentialContactAdapter:
    def __init__(self, model, data, cpu_model, motor, iterations=100):
        assert not model.is_sparse, 'Prototype uses existing dense inertia factor'
        flags=int(types.DisableBit.LIMIT)|int(types.DisableBit.EQUALITY)
        assert model.opt.disableflags&flags==flags, 'Isolated contact test requires limits/equalities explicitly disabled'
        assert cpu_model.neq==0 and cpu_model.ntendon==0
        assert np.all(cpu_model.geom_friction[:,0]==cpu_model.geom_friction[0,0]), 'Uniform pair friction only in prototype'
        self.model=model; self.data=data; self.motor=motor; self.iterations=iterations
        self.original_cone=model.opt.cone; model.opt.cone=int(types.ConeType.ELLIPTIC)
        dev=data.qvel.device; n=data.nworld; nv=cpu_model.nv; nc=4*cpu_model.ngeom
        p=ContactProblem(); p.nv=nv; p.nmotor=len(motor.ids); p.dt=model.opt.timestep
        p.dofs=motor.dofs; p.gains=motor.gains; p.caps=motor.upper
        zero=lambda shape,dtype=float: wp.zeros(shape,dtype=dtype,device=dev)
        p.ncontact=zero(n,int); p.inv=zero((n,nv,nv)); p.free=zero((n,nv)); p.commands=zero((n,p.nmotor))
        p.friction=zero(n); p.J=zero((n,nc,3,nv)); p.response=zero((n,nc,3,nv)); p.diagonal=zero((n,nc,3))
        p.velocity=zero((n,nv)); p.motor_impulse=zero((n,p.nmotor)); p.contact_impulse=zero((n,nc,3)); p.stats=zero((n,1))
        self.p=p; self.capacity=nc; self.error=zero(n,int); self.rowmap=zero((n,nc,3),int)
        self.identity=wp.array(np.eye(nv,dtype=np.float32),device=dev)
        self.inverse_kernel=make_inverse(nv); self.iterate_kernel=make_tiled_iteration(nv,p.nmotor)
        self.installed=False

    def solve(self,m,d):
        assert d is self.data
        p=self.p; dev=d.qvel.device
        p.ncontact.zero_(); p.J.zero_(); self.error.zero_(); d.efc.force.zero_()
        wp.launch(initialize,dim=(d.nworld,p.nv),inputs=[p,d.qvel,d.qacc_smooth,d.ctrl,self.motor.acts],device=dev)
        wp.launch_tiled(self.inverse_kernel,dim=d.nworld,inputs=[d.qLD,self.identity,p.inv],block_dim=32,device=dev)
        wp.launch(contacts,dim=d.contact.worldid.shape[0],inputs=[p,self.capacity,types.SPARSE_CONSTRAINT_JACOBIAN,d.nacon,
            d.contact.worldid,d.contact.dim,d.contact.type,d.contact.efc_address,d.efc.J,d.efc.J_rownnz,d.efc.J_rowadr,d.efc.J_colind,
            d.contact.friction,self.rowmap,self.error],device=dev)
        wp.launch(bound_counts,dim=d.nworld,inputs=[p,self.capacity],device=dev)
        wp.launch(prepare_response,dim=(d.nworld,self.capacity,3,p.nv),inputs=[p],device=dev)
        wp.launch(prepare_diagonal,dim=(d.nworld,self.capacity,3),inputs=[p],device=dev)
        wp.launch_tiled(self.iterate_kernel,dim=d.nworld,inputs=[p,self.iterations],block_dim=32,device=dev)
        wp.launch(finish,dim=(d.nworld,p.nv),inputs=[p,d.qvel,d.qacc,d.qM,d.qfrc_constraint,d.efc.force,self.motor.rows.rowids,self.rowmap,self.error],device=dev)

    def install(self):
        assert not getattr(self.model,'transfer_contact_test',None)
        if not getattr(solver.solve,'_transfer_contact_dispatch',False):
            original=solver.solve
            def dispatch(m,d):
                custom=getattr(m,'transfer_contact_test',None)
                if custom is not None and custom.data is d: return custom.solve(m,d)
                return original(m,d)
            dispatch._transfer_contact_dispatch=True
            solver.solve=dispatch
        self.model.transfer_contact_test=self; self.installed=True

    def restore(self):
        if self.installed:
            self.model.transfer_contact_test=None; self.model.opt.cone=self.original_cone; self.installed=False
