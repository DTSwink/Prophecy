"""Contained MJWarp contact-law experiment, NOT a training default.

Dense single-articulation models only. Limits are disabled unless the explicit
soft-MJ-limit control is selected. Existing motor rows supply actuation. Both
frictionless and three-row frictional contacts are supported. This is a diagnostic
integration, not a complete Jolt replacement: manifold friction and position
projection are still outstanding.
"""
import numpy as np
import warp as wp
from mujoco_warp._src import solver, types
from sequential_contact_gpu import (ContactProblem, prepare_response, prepare_diagonal, make_tiled_iteration,
                                    prepare_limit_response, prepare_limit_diagonal)


@wp.kernel(enable_backward=False)
def soft_limits(p: ContactProblem, nefc: wp.array(dtype=int), kind: wp.array2d(dtype=int),
                J: wp.array3d(dtype=float), D: wp.array2d(dtype=float), aref: wp.array2d(dtype=float),
                sparse: bool, nnz: wp.array2d(dtype=int), adr: wp.array2d(dtype=int), cols: wp.array3d(dtype=int),
                qvel: wp.array2d(dtype=float), motorrows: wp.array2d(dtype=int), mapping: wp.array2d(dtype=int),
                error: wp.array(dtype=int), hard_control: bool, jolt_axes:bool,
                joint_kind:wp.array(dtype=int),row_joint:wp.array2d(dtype=int)):
    # Diagnostic control: preserve MJ's angular-limit response while replacing
    # contact friction. Rows remain soft; this is not yet the Jolt limit model.
    w=wp.tid()
    for row in range(nefc[w]):
        k=kind[w,row]
        if k!=int(types.ConstraintType.LIMIT_JOINT) and k!=int(types.ConstraintType.EQUALITY): continue
        motor=bool(False)
        for a in range(p.nmotor):
            if row==motorrows[w,a]: motor=True
        if motor: continue
        if jolt_axes and joint_kind[row_joint[w,row]]==1:continue
        slot=p.nlimit[w]
        if slot>=p.limit_J.shape[1]:
            error[w]=3
            continue
        p.nlimit[w]=slot+1;mapping[w,slot]=row
        speed=float(0.)
        if sparse:
            start=adr[w,row]
            for i in range(nnz[w,row]):
                j=cols[w,0,start+i];value=J[w,0,start+i]
                p.limit_J[w,slot,j]=value;speed+=value*qvel[w,j]
        else:
            for j in range(p.nv):
                value=J[w,row,j];p.limit_J[w,slot,j]=value
                speed+=value*qvel[w,j]
        p.limit_target[w,slot]=speed+p.dt[0]*aref[w,row]
        p.limit_compliance[w,slot]=1./D[w,row]
        if hard_control:
            # Isolation control only: hard velocity response using the current
            # MJ PHAT row direction. Position projection is tested separately.
            p.limit_target[w,slot]=0.
            p.limit_compliance[w,slot]=0.
        p.limit_bilateral[w,slot]=int(k==int(types.ConstraintType.EQUALITY))


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
             distance: wp.array(dtype=float), margin: wp.array(dtype=float),
             rows: wp.array2d(dtype=int), efcJ: wp.array3d(dtype=float),
             nnz: wp.array2d(dtype=int), adr: wp.array2d(dtype=int), cols: wp.array3d(dtype=int),
             friction: wp.array(dtype=types.vec5), rowmap: wp.array3d(dtype=int), error: wp.array(dtype=int), contactids: wp.array2d(dtype=int)):
    c=wp.tid()
    if c>=nacon[0] or not (kind[c]&int(types.ContactType.CONSTRAINT)): return
    # Collision candidates outside the active margin retain old/zero row
    # addresses. CONSTRAINT alone does not mean an equation was generated.
    # This profile also intentionally excludes speculative positive gaps.
    if distance[c]>=0. or distance[c]>=margin[c]: return
    if rows[c,0]<0: return
    w=worldid[c]
    if dim[c]!=1 and dim[c]!=3:
        error[w]=1
        return
    slot=wp.atomic_add(p.ncontact,w,1)
    if slot>=capacity:
        error[w]=1
        return
    contactids[w,slot]=c
    p.friction[w,slot]=0.
    if dim[c]==3: p.friction[w,slot]=friction[c][0]
    for a in range(dim[c]):
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
           contactrows: wp.array3d(dtype=int), limitrows: wp.array2d(dtype=int), error: wp.array(dtype=int)):
    w,j=wp.tid(); dt=p.dt[0]
    qacc[w,j]=(p.velocity[w,j]-qvel[w,j])/dt
    if not wp.isfinite(qacc[w,j]): error[w]=4
    force=float(0.)
    for i in range(p.nv): force+=mass[w,j,i]*(p.velocity[w,i]-p.free[w,i])/dt
    constraint_force[w,j]=force
    if j<p.nmotor: rowforce[w,motorrows[w,j]]=p.motor_impulse[w,j]/dt
    if j==0:
        for c in range(p.nlimit[w]):
            if limitrows[w,c]>=0:rowforce[w,limitrows[w,c]]=p.limit_impulse[w,c]/dt
        for c in range(wp.min(p.ncontact[w],p.contact_impulse.shape[1])):
            axes=int(1)
            if p.friction[w,c]>0.: axes=3
            for a in range(axes):
                row=contactrows[w,c,a]
                if row>=0: rowforce[w,row]=p.contact_impulse[w,c,a]/dt
    # A diagnostic caller must check error before accepting any output. Do not
    # silently truncate contacts or pretend unsupported constraint types worked.


class SequentialContactAdapter:
    def __init__(self, model, data, cpu_model, motor, iterations=100, allow_soft_limits=False, relaxation=1., hard_limit_control=False, block_motors=False, manifolds=False, jolt_limit_axes=False, seed_iterations=50):
        assert not model.is_sparse, 'Prototype uses existing dense inertia factor'
        flags=int(types.DisableBit.LIMIT)|int(types.DisableBit.EQUALITY)
        assert allow_soft_limits or model.opt.disableflags&flags==flags, 'Limits require explicit diagnostic opt-in'
        assert cpu_model.neq==0 and cpu_model.ntendon==0
        self.model=model; self.data=data; self.motor=motor; self.iterations=iterations
        assert seed_iterations>=0
        self.seed_iterations=seed_iterations
        self.allow_soft_limits=allow_soft_limits
        assert not hard_limit_control or allow_soft_limits
        self.hard_limit_control=hard_limit_control
        assert not jolt_limit_axes or hard_limit_control
        self.jolt_limit_axes=jolt_limit_axes
        if jolt_limit_axes:
            self.limit_metadata=model.uefn_compound_limits
            np.testing.assert_array_equal(self.limit_metadata.modes.numpy(),1)
        self.original_cone=model.opt.cone; model.opt.cone=int(types.ConeType.ELLIPTIC)
        dev=data.qvel.device; n=data.nworld; nv=cpu_model.nv; nc=4*cpu_model.ngeom
        assert 0.<relaxation<=1.
        p=ContactProblem(); p.nv=nv; p.nmotor=len(motor.ids); p.dt=model.opt.timestep; p.relaxation=relaxation
        p.dofs=motor.dofs; p.gains=motor.gains; p.caps=motor.upper
        zero=lambda shape,dtype=float: wp.zeros(shape,dtype=dtype,device=dev)
        p.ncontact=zero(n,int); p.inv=zero((n,nv,nv)); p.free=zero((n,nv)); p.commands=zero((n,p.nmotor))
        p.friction=zero((n,nc)); p.J=zero((n,nc,3,nv)); p.response=zero((n,nc,3,nv)); p.diagonal=zero((n,nc,3))
        p.velocity=zero((n,nv)); p.motor_impulse=zero((n,p.nmotor)); p.contact_impulse=zero((n,nc,3)); p.stats=zero((n,1))
        nl=3*cpu_model.njnt
        p.nlimit=zero(n,int);p.limit_J=zero((n,nl,nv));p.limit_response=zero((n,nl,nv))
        p.limit_diagonal=zero((n,nl));p.limit_target=zero((n,nl));p.limit_compliance=zero((n,nl))
        p.limit_bilateral=zero((n,nl),int);p.limit_impulse=zero((n,nl));self.limitrows=zero((n,nl),int)
        self.p=p; self.capacity=nc; self.error=zero(n,int); self.rowmap=zero((n,nc,3),int)
        p.solver_error=self.error;p.fallback_count=zero(n,int);p.fallback_steps=zero(n,int)
        self.contactids=zero((n,nc),int)
        if manifolds:
            from contact_manifolds_gpu import allocate
            p.manifold=allocate(n,nc,nv,dev);p.manifold.contact_ids=self.contactids
            self.body_mass=wp.array(cpu_model.body_mass.astype(np.float32),device=dev)
            self.body_inertia=wp.array(cpu_model.body_inertia.astype(np.float32),dtype=wp.vec3,device=dev)
        self.identity=wp.array(np.eye(nv,dtype=np.float32),device=dev)
        self.inverse_kernel=make_inverse(nv); self.iterate_kernel=make_tiled_iteration(nv,p.nmotor)
        self.block_motors=block_motors
        if block_motors:
            from block_contact_gpu import make_block_iteration
            self.block_kernel=make_block_iteration(nv,p.nmotor)
            self.fallback_kernel=make_tiled_iteration(nv,p.nmotor,fallback=True)
        self.installed=False

    def solve(self,m,d):
        assert d is self.data
        p=self.p; dev=d.qvel.device
        # Keep failures latched: a later successful substep must not conceal an
        # earlier unsupported contact from the policy-step validation.
        p.ncontact.zero_();p.nlimit.zero_();p.limit_J.zero_(); p.J.zero_(); d.efc.force.zero_()
        wp.launch(initialize,dim=(d.nworld,p.nv),inputs=[p,d.qvel,d.qacc_smooth,d.ctrl,self.motor.acts],device=dev)
        wp.launch_tiled(self.inverse_kernel,dim=d.nworld,inputs=[d.qLD,self.identity,p.inv],block_dim=32,device=dev)
        if self.allow_soft_limits:
            wp.launch(soft_limits,dim=d.nworld,inputs=[p,d.nefc,d.efc.type,d.efc.J,d.efc.D,d.efc.aref,
                      types.SPARSE_CONSTRAINT_JACOBIAN,d.efc.J_rownnz,d.efc.J_rowadr,d.efc.J_colind,d.qvel,
                      self.motor.rows.rowids,self.limitrows,self.error,self.hard_limit_control,self.jolt_limit_axes,m.jnt_type,d.efc.id],device=dev)
            if self.jolt_limit_axes:
                from jolt_limit_directions import append
                limits=self.limit_metadata
                wp.launch(append,dim=d.nworld,inputs=[p,d.qpos,limits.joints,limits.reference,
                    limits.angles,m.jnt_qposadr,m.jnt_dofadr,self.limitrows,self.error],device=dev)
            wp.launch(prepare_limit_response,dim=(d.nworld,p.limit_J.shape[1],p.nv),inputs=[p],device=dev)
            wp.launch(prepare_limit_diagonal,dim=(d.nworld,p.limit_J.shape[1]),inputs=[p],device=dev)
        wp.launch(contacts,dim=d.contact.worldid.shape[0],inputs=[p,self.capacity,types.SPARSE_CONSTRAINT_JACOBIAN,d.nacon,
            d.contact.worldid,d.contact.dim,d.contact.type,d.contact.dist,d.contact.includemargin,d.contact.efc_address,d.efc.J,d.efc.J_rownnz,d.efc.J_rowadr,d.efc.J_colind,
            d.contact.friction,self.rowmap,self.error,self.contactids],device=dev)
        wp.launch(bound_counts,dim=d.nworld,inputs=[p,self.capacity],device=dev)
        wp.launch(prepare_response,dim=(d.nworld,self.capacity,3,p.nv),inputs=[p],device=dev)
        wp.launch(prepare_diagonal,dim=(d.nworld,self.capacity,3),inputs=[p],device=dev)
        if p.manifold.enabled:
            from contact_manifolds_gpu import prepare,replace_point_friction
            prepare(p.manifold,p.ncontact,p.friction,m,d,p.inv,self.error,self.body_mass,self.body_inertia)
            wp.launch(replace_point_friction,dim=(d.nworld,self.capacity,p.nv),inputs=[p.manifold,p.ncontact,p.friction,p.J,p.diagonal],device=dev)
            wp.launch(prepare_response,dim=(d.nworld,self.capacity,3,p.nv),inputs=[p],device=dev)
        if self.block_motors:
            wp.launch_tiled(self.iterate_kernel,dim=d.nworld,inputs=[p,self.seed_iterations],block_dim=32,device=dev)
            wp.launch_tiled(self.block_kernel,dim=d.nworld,inputs=[p,d.qM,self.identity,self.iterations,self.error],block_dim=32,device=dev)
            wp.launch_tiled(self.fallback_kernel,dim=d.nworld,inputs=[p,3000],block_dim=32,device=dev)
        else:
            wp.launch_tiled(self.iterate_kernel,dim=d.nworld,inputs=[p,self.iterations],block_dim=32,device=dev)
        wp.launch(finish,dim=(d.nworld,p.nv),inputs=[p,d.qvel,d.qacc,d.qM,d.qfrc_constraint,d.efc.force,self.motor.rows.rowids,self.rowmap,self.limitrows,self.error],device=dev)

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
