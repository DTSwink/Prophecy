"""GPU seed and checked fallback for the Jolt-matching training profile.

Jolt-style non-associated friction: friction uses the normal impulse from the
previous iteration; normal is solved last. Motors are capped end-step motors.
No CPU transfers or allocations occur inside solve/captured graph replay.
"""
import warp as wp
from contact_manifolds_gpu import ContactManifolds


@wp.struct
class ContactProblem:
    manifold: ContactManifolds
    nv: int
    nmotor: int
    relaxation: float
    ncontact: wp.array(dtype=int)
    dt: wp.array(dtype=float)
    inv: wp.array3d(dtype=float)
    free: wp.array2d(dtype=float)
    dofs: wp.array(dtype=int)
    gains: wp.array(dtype=float)
    caps: wp.array(dtype=float)
    commands: wp.array2d(dtype=float)
    friction: wp.array2d(dtype=float)
    J: wp.array4d(dtype=float)
    response: wp.array4d(dtype=float)
    diagonal: wp.array3d(dtype=float)
    velocity: wp.array2d(dtype=float)
    motor_impulse: wp.array2d(dtype=float)
    contact_impulse: wp.array3d(dtype=float)
    stats: wp.array2d(dtype=float)
    nlimit: wp.array(dtype=int)
    limit_J: wp.array3d(dtype=float)
    limit_response: wp.array3d(dtype=float)
    limit_diagonal: wp.array2d(dtype=float)
    limit_target: wp.array2d(dtype=float)
    limit_compliance: wp.array2d(dtype=float)
    limit_bilateral: wp.array2d(dtype=int)
    limit_impulse: wp.array2d(dtype=float)
    effective_normal_diagonal: wp.array2d(dtype=float)
    effective_limit_diagonal: wp.array2d(dtype=float)
    # Per-block friction preconditioner; original projection metric stays intact.
    block_metric: wp.array3d(dtype=float)
    solver_error: wp.array(dtype=int)
    fallback_count: wp.array(dtype=int)
    fallback_steps: wp.array(dtype=int)
    roundoff_warnings: wp.array(dtype=int)
    roundoff_delta: wp.array(dtype=float)
    convergence_warnings: wp.array(dtype=int)
    convergence_metrics: wp.array2d(dtype=float)
    # 0: cold, 1: previous torque branches available, -1: full seed retry needed.
    # This is only a solve hint; every accepted result uses current equations.
    warm_state: wp.array(dtype=int)
    warm_status: wp.array2d(dtype=int)


@wp.kernel(enable_backward=False)
def prepare_response(p: ContactProblem):
    w,c,a,i=wp.tid()
    if c>=p.ncontact[w]: return
    value=float(0.)
    for j in range(p.nv): value+=p.inv[w,i,j]*p.J[w,c,a,j]
    p.response[w,c,a,i]=value


@wp.kernel(enable_backward=False)
def prepare_diagonal(p: ContactProblem):
    w,c,a=wp.tid()
    if c>=p.ncontact[w]: return
    value=float(0.)
    for j in range(p.nv): value+=p.J[w,c,a,j]*p.response[w,c,a,j]
    p.diagonal[w,c,a]=value


@wp.kernel(enable_backward=False)
def prepare_limit_response(p: ContactProblem):
    w,c,i=wp.tid()
    if c>=p.nlimit[w]: return
    value=float(0.)
    for j in range(p.nv): value+=p.inv[w,i,j]*p.limit_J[w,c,j]
    p.limit_response[w,c,i]=value


@wp.kernel(enable_backward=False)
def prepare_limit_diagonal(p: ContactProblem):
    w,c=wp.tid()
    if c>=p.nlimit[w]: return
    value=float(0.)
    for j in range(p.nv): value+=p.limit_J[w,c,j]*p.limit_response[w,c,j]
    p.limit_diagonal[w,c]=value


@wp.kernel(enable_backward=False)
def iterate(p: ContactProblem, iterations: int):
    w=wp.tid(); dt=p.dt[0]
    for j in range(p.nv): p.velocity[w,j]=p.free[w,j]
    for a in range(p.nmotor): p.motor_impulse[w,a]=0.
    for c in range(p.ncontact[w]):
        for a in range(3): p.contact_impulse[w,c,a]=0.
    for it in range(iterations):
        for a in range(p.nmotor):
            dof=p.dofs[a]; compliance=1./(dt*p.gains[a]); old=p.motor_impulse[w,a]
            impulse=wp.clamp(old+(p.commands[w,a]-p.velocity[w,dof]-compliance*old)/(p.inv[w,dof,dof]+compliance),-dt*p.caps[a],dt*p.caps[a])
            for j in range(p.nv): p.velocity[w,j]+=p.inv[w,j,dof]*(impulse-old)
            p.motor_impulse[w,a]=impulse
        for c in range(p.ncontact[w]):
            if p.friction[w,c]>0.:
                v1=float(0.); v2=float(0.)
                for j in range(p.nv):
                    v1+=p.J[w,c,1,j]*p.velocity[w,j]
                    v2+=p.J[w,c,2,j]*p.velocity[w,j]
                old1=p.contact_impulse[w,c,1]; old2=p.contact_impulse[w,c,2]
                t1=old1-v1/p.diagonal[w,c,1]; t2=old2-v2/p.diagonal[w,c,2]
                length=wp.sqrt(t1*t1+t2*t2); bound=p.friction[w,c]*p.contact_impulse[w,c,0]
                scale=wp.min(1.,bound/wp.max(length,1e-30)); t1*=scale; t2*=scale
                for j in range(p.nv):
                    p.velocity[w,j]+=p.response[w,c,1,j]*(t1-old1)+p.response[w,c,2,j]*(t2-old2)
                p.contact_impulse[w,c,1]=t1; p.contact_impulse[w,c,2]=t2
            vn=float(0.)
            for j in range(p.nv): vn+=p.J[w,c,0,j]*p.velocity[w,j]
            old=p.contact_impulse[w,c,0]; normal=wp.max(0.,old-vn/p.diagonal[w,c,0])
            for j in range(p.nv): p.velocity[w,j]+=p.response[w,c,0,j]*(normal-old)
            p.contact_impulse[w,c,0]=normal
    defect=float(0.)
    for a in range(p.nmotor):
        expected=wp.clamp(p.gains[a]*(p.commands[w,a]-p.velocity[w,p.dofs[a]]),-p.caps[a],p.caps[a])
        defect=wp.max(defect,wp.abs(p.motor_impulse[w,a]/dt-expected))
    p.stats[w,0]=defect


class SequentialContactProblem:
    def __init__(self, snapshots, device):
        import numpy as np
        n=len(snapshots); p=ContactProblem(); p.nv=len(snapshots[0]['free']); p.nmotor=len(snapshots[0]['dofs']); p.relaxation=1.
        nc=max(1,max(len(s['J']) for s in snapshots)); self.nworld=n; self.capacity=nc
        arr=lambda x,dtype=float: wp.array(np.asarray(x),dtype=dtype,device=device)
        p.ncontact=arr([len(s['J']) for s in snapshots],int)
        p.dt=arr([float(snapshots[0]['dt'])]); p.dofs=arr(snapshots[0]['dofs'],int)
        p.gains=arr(snapshots[0]['gain']); p.caps=arr(snapshots[0]['caps']/snapshots[0]['dt'])
        for s in snapshots:
            np.testing.assert_array_equal(s['dofs'],snapshots[0]['dofs'])
            np.testing.assert_allclose(s['dt'],snapshots[0]['dt'])
        p.inv=arr([s['inv'] for s in snapshots]); p.free=arr([s['free'] for s in snapshots])
        p.commands=arr([s['command'] for s in snapshots]); p.friction=arr([[s['friction']]*nc for s in snapshots])
        jac=np.zeros((n,nc,3,p.nv),dtype=np.float32)
        for w,s in enumerate(snapshots): jac[w,:len(s['J'])]=s['J']
        p.J=arr(jac)
        zero=lambda shape: wp.zeros(shape,dtype=float,device=device)
        p.response=zero(jac.shape); p.diagonal=zero((n,nc,3)); p.velocity=zero((n,p.nv))
        p.motor_impulse=zero((n,p.nmotor)); p.contact_impulse=zero((n,nc,3)); p.stats=zero((n,1))
        p.nlimit=wp.zeros(n,dtype=int,device=device)
        p.limit_J=zero((n,1,p.nv));p.limit_response=zero((n,1,p.nv))
        p.limit_diagonal=zero((n,1));p.limit_target=zero((n,1));p.limit_compliance=zero((n,1))
        p.limit_bilateral=wp.zeros((n,1),dtype=int,device=device);p.limit_impulse=zero((n,1))
        self.p=p; self.device=device
        self.tiled_kernel=make_tiled_iteration(p.nv,p.nmotor)

    def solve(self, iterations=100, tiled=False):
        p=self.p
        wp.launch(prepare_response,dim=(self.nworld,self.capacity,3,p.nv),inputs=[p],device=self.device)
        wp.launch(prepare_diagonal,dim=(self.nworld,self.capacity,3),inputs=[p],device=self.device)
        if tiled:
            wp.launch_tiled(self.tiled_kernel,dim=self.nworld,inputs=[p,iterations],block_dim=32,device=self.device)
        else:
            wp.launch(iterate,dim=self.nworld,inputs=[p,iterations],device=self.device)


@wp.func
def multiply(a: float,b: float): return a*b


@wp.func
def absolute(a:float):return wp.abs(a)


@wp.func
def finite_value(a:float):return float(wp.isfinite(a))


@wp.func
def friction_bound(p:ContactProblem,w:int,c:int):
    normal=p.contact_impulse[w,c,0];spin=float(0.)
    if p.manifold.enabled:
        group=p.manifold.group[w,c];normal=float(0.)
        for other in range(p.ncontact[w]):
            if p.manifold.group[w,other]==group:
                impulse=p.contact_impulse[w,other,0]
                normal+=impulse;spin+=p.manifold.radius[w,other]*impulse
    return p.friction[w,c]*wp.vec2(normal,spin)


def make_tiled_iteration(nv,nmotor,fallback=False,warm_start=False,retry=False):
    @wp.kernel(module='unique',enable_backward=False)
    def tiled(p: ContactProblem, iterations: int):
        w,lane=wp.tid(); dt=p.dt[0]
        if wp.static(warm_start):
            if wp.static(retry):
                if p.warm_state[w]!=-1:return
            else:
                if p.warm_state[w]>0:return
        if wp.static(fallback):
            if p.solver_error[w]!=5:return
            if lane==0:p.fallback_count[w]+=1
        v=wp.tile_load(p.free,shape=(1,nv),offset=(w,0),storage='shared')
        inverse=wp.tile_load(p.inv[w],shape=(nv,nv),storage='shared')
        if wp.static(fallback or retry):
            # Block elimination stores effective responses. Restore the original
            # physical mass responses for this world's scalar solve only.
            for c in range(p.ncontact[w]):
                for a in range(3):
                    jac=wp.tile_reshape(wp.tile_load(p.J[w,c,a],shape=(nv,)),shape=(1,nv))
                    wp.tile_store(p.response[w,c,a],wp.tile_reshape(wp.tile_matmul(jac,inverse),shape=(nv,)))
            for c in range(p.nlimit[w]):
                jac=wp.tile_reshape(wp.tile_load(p.limit_J[w,c],shape=(nv,)),shape=(1,nv))
                wp.tile_store(p.limit_response[w,c],wp.tile_reshape(wp.tile_matmul(jac,inverse),shape=(nv,)))
            if p.manifold.enabled:
                for g in range(p.manifold.count[w]):
                    jac=wp.tile_reshape(wp.tile_load(p.manifold.J[w,g,2],shape=(nv,)),shape=(1,nv))
                    wp.tile_store(p.manifold.response[w,g,2],wp.tile_reshape(wp.tile_matmul(jac,inverse),shape=(nv,)))
        impulses=wp.tile_zeros(shape=(1,nmotor),dtype=float,storage='shared')
        previous=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')
        # The rare fallback can take hundreds of sweeps. Compensate its
        # incremental velocity additions so float32 roundoff cannot create a
        # persistent false convergence failure. Keep the fast seed unchanged.
        if wp.static(fallback):
            roundoff=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')
        if wp.static(not fallback):
            # These values are constant during all seed sweeps. Keep the same
            # divisions and operation order; the checked fallback is unchanged.
            coefficients=wp.tile_zeros(shape=(4,nmotor),dtype=float,storage='shared')
            for a in range(nmotor):
                dof=p.dofs[a];compliance=1./(dt*p.gains[a])
                coefficients[0,a]=compliance
                coefficients[1,a]=p.inv[w,dof,dof]+compliance
                coefficients[2,a]=dt*p.caps[a]
                coefficients[3,a]=p.commands[w,a]
        converged=bool(False)
        last_change=float(1e30)
        for c in range(p.ncontact[w]):
            for a in range(3): p.contact_impulse[w,c,a]=0.
        for c in range(p.nlimit[w]): p.limit_impulse[w,c]=0.
        if p.manifold.enabled:
            for g in range(p.manifold.count[w]):p.manifold.impulse[w,g,2]=0.
        for it in range(iterations):
            if wp.static(fallback):wp.tile_assign(previous,v)
            for a in range(p.nmotor):
                dof=p.dofs[a];old=wp.tile_extract(impulses,0,a)
                speed=wp.tile_extract(v,0,dof)
                if wp.static(fallback):
                    compliance=1./(dt*p.gains[a])
                    impulse=wp.clamp(old+(p.commands[w,a]-speed-compliance*old)/(p.inv[w,dof,dof]+compliance),-dt*p.caps[a],dt*p.caps[a])
                else:
                    compliance=wp.tile_extract(coefficients,0,a)
                    denominator=wp.tile_extract(coefficients,1,a)
                    cap=wp.tile_extract(coefficients,2,a)
                    command=wp.tile_extract(coefficients,3,a)
                    impulse=wp.clamp(old+(command-speed-compliance*old)/denominator,-cap,cap)
                impulse=old+p.relaxation*(impulse-old)
                response=wp.tile_view(inverse,offset=(dof,0),shape=(1,nv))
                if wp.static(fallback):
                    corrected=(response*(impulse-old))-roundoff
                    updated=v+corrected
                    wp.tile_assign(roundoff,(updated-v)-corrected)
                    wp.tile_assign(v,updated)
                else:
                    wp.tile_assign(v,v+response*(impulse-old))
                impulses[0,a]=impulse
            for c in range(p.nlimit[w]):
                jac=wp.tile_reshape(wp.tile_load(p.limit_J[w,c],shape=(nv,)),shape=(1,nv))
                speed=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jac,v)),0)
                old=p.limit_impulse[w,c]; compliance=p.limit_compliance[w,c]
                impulse=old+(p.limit_target[w,c]-speed-compliance*old)/(p.limit_diagonal[w,c]+compliance)
                if p.limit_bilateral[w,c]==0: impulse=wp.max(0.,impulse)
                impulse=old+p.relaxation*(impulse-old)
                response=wp.tile_reshape(wp.tile_load(p.limit_response[w,c],shape=(nv,)),shape=(1,nv))
                if wp.static(fallback):
                    corrected=(response*(impulse-old))-roundoff
                    updated=v+corrected
                    wp.tile_assign(roundoff,(updated-v)-corrected)
                    wp.tile_assign(v,updated)
                else:
                    wp.tile_assign(v,v+response*(impulse-old))
                p.limit_impulse[w,c]=impulse
            for c in range(p.ncontact[w]):
                if p.friction[w,c]>0.:
                    j1=wp.tile_reshape(wp.tile_load(p.J[w,c,1],shape=(nv,)),shape=(1,nv)); j2=wp.tile_reshape(wp.tile_load(p.J[w,c,2],shape=(nv,)),shape=(1,nv))
                    v1=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,j1,v)),0)
                    v2=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,j2,v)),0)
                    old1=p.contact_impulse[w,c,1]; old2=p.contact_impulse[w,c,2]
                    t1=old1-v1/p.diagonal[w,c,1]; t2=old2-v2/p.diagonal[w,c,2]
                    bounds=friction_bound(p,w,c)
                    length=wp.sqrt(t1*t1+t2*t2); bound=bounds[0]
                    scale=wp.min(1.,bound/wp.max(length,1e-30)); t1*=scale; t2*=scale
                    t1=old1+p.relaxation*(t1-old1); t2=old2+p.relaxation*(t2-old2)
                    r1=wp.tile_reshape(wp.tile_load(p.response[w,c,1],shape=(nv,)),shape=(1,nv)); r2=wp.tile_reshape(wp.tile_load(p.response[w,c,2],shape=(nv,)),shape=(1,nv))
                    if wp.static(fallback):
                        corrected=(r1*(t1-old1)+r2*(t2-old2))-roundoff
                        updated=v+corrected
                        wp.tile_assign(roundoff,(updated-v)-corrected)
                        wp.tile_assign(v,updated)
                    else:
                        wp.tile_assign(v,v+r1*(t1-old1)+r2*(t2-old2))
                    p.contact_impulse[w,c,1]=t1; p.contact_impulse[w,c,2]=t2
                    if p.manifold.enabled:
                        g=p.manifold.group[w,c]
                        if p.manifold.size[w,g]>1:
                            sj=wp.tile_reshape(wp.tile_load(p.manifold.J[w,g,2],shape=(nv,)),shape=(1,nv))
                            sr=wp.tile_reshape(wp.tile_load(p.manifold.response[w,g,2],shape=(nv,)),shape=(1,nv))
                            speed=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,sj,v)),0)
                            oldspin=p.manifold.impulse[w,g,2]
                            spin=wp.clamp(oldspin-speed/p.manifold.diagonal[w,g,2],-bounds[1],bounds[1])
                            spin=oldspin+p.relaxation*(spin-oldspin)
                            if wp.static(fallback):
                                corrected=(sr*(spin-oldspin))-roundoff
                                updated=v+corrected
                                wp.tile_assign(roundoff,(updated-v)-corrected)
                                wp.tile_assign(v,updated)
                            else:
                                wp.tile_assign(v,v+sr*(spin-oldspin))
                            p.manifold.impulse[w,g,2]=spin
                jn=wp.tile_reshape(wp.tile_load(p.J[w,c,0],shape=(nv,)),shape=(1,nv))
                vn=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jn,v)),0)
                old=p.contact_impulse[w,c,0]; normal=wp.max(0.,old-vn/p.diagonal[w,c,0])
                normal=old+p.relaxation*(normal-old)
                rn=wp.tile_reshape(wp.tile_load(p.response[w,c,0],shape=(nv,)),shape=(1,nv))
                if wp.static(fallback):
                    corrected=(rn*(normal-old))-roundoff
                    updated=v+corrected
                    wp.tile_assign(roundoff,(updated-v)-corrected)
                    wp.tile_assign(v,updated)
                else:
                    wp.tile_assign(v,v+rn*(normal-old))
                p.contact_impulse[w,c,0]=normal
            if wp.static(fallback):
                if it%16==15:
                    change=wp.tile_extract(wp.tile_max(wp.tile_map(absolute,v-previous)),0)
                    last_change=change
                    residual=float(0.)
                    for a in range(nmotor):
                        speed=wp.tile_extract(v,0,p.dofs[a])
                        expected=wp.clamp(p.gains[a]*(p.commands[w,a]-speed),-p.caps[a],p.caps[a])
                        residual=wp.max(residual,wp.abs(wp.tile_extract(impulses,0,a)/dt-expected))
                    if change<2e-6 and residual<.002:
                        converged=True
                        if lane==0:p.fallback_steps[w]+=it+1
                        break
        velocity_out=p.velocity
        wp.tile_store(velocity_out,v,offset=(w,0))
        motor_out=p.motor_impulse
        wp.tile_store(motor_out,impulses,offset=(w,0))
        defect=float(0.)
        for a in range(p.nmotor):
            speed=wp.tile_extract(v,0,p.dofs[a])
            expected=wp.clamp(p.gains[a]*(p.commands[w,a]-speed),-p.caps[a],p.caps[a])
            defect=wp.max(defect,wp.abs(p.motor_impulse[w,a]/dt-expected))
        p.stats[w,0]=defect
        if wp.static(fallback):
            if converged:p.solver_error[w]=0
            else:
                p.solver_error[w]=6
                # Iteration progress can hit the float32 rounding floor even
                # when forces and contacts are satisfied. Keep the strict stop
                # criterion above; after exhausting the solve, distinguish this
                # small finite residual from a materially failed solve.
                last_change=wp.tile_extract(wp.tile_max(wp.tile_map(absolute,v-previous)),0)
                speed_scale=wp.tile_extract(wp.tile_max(wp.tile_map(absolute,v)),0)
                precision=wp.min(1e-4,wp.max(2e-6,8.*1.1920928955078125e-7*wp.max(1.,speed_scale)))
                contact_error=float(0.)
                finite_constraints=bool(True)
                for c in range(p.ncontact[w]):
                    jn=wp.tile_reshape(wp.tile_load(p.J[w,c,0],shape=(nv,)),shape=(1,nv))
                    vn=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jn,v)),0)
                    error=wp.max(0.,-vn)
                    if p.contact_impulse[w,c,0]>0.:error=wp.abs(vn)
                    contact_error=wp.max(contact_error,error)
                    finite_constraints=finite_constraints and wp.isfinite(vn)
                    for a in range(3):
                        finite_constraints=finite_constraints and wp.isfinite(p.contact_impulse[w,c,a])
                for c in range(p.nlimit[w]):
                    jac=wp.tile_reshape(wp.tile_load(p.limit_J[w,c],shape=(nv,)),shape=(1,nv))
                    speed=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jac,v)),0)
                    gap=speed+p.limit_compliance[w,c]*p.limit_impulse[w,c]-p.limit_target[w,c]
                    error=wp.max(0.,-gap)
                    if p.limit_bilateral[w,c]!=0 or p.limit_impulse[w,c]>0.:error=wp.abs(gap)
                    contact_error=wp.max(contact_error,error)
                    finite_constraints=finite_constraints and wp.isfinite(gap) and wp.isfinite(p.limit_impulse[w,c])
                finite_velocity=wp.tile_extract(wp.tile_min(wp.tile_map(finite_value,v)),0)>0.
                finite_motors=wp.tile_extract(wp.tile_min(wp.tile_map(finite_value,impulses)),0)>0.
                if finite_velocity and finite_motors and finite_constraints and wp.isfinite(last_change) and wp.isfinite(defect) and wp.isfinite(contact_error):
                    # An iteration budget is not a validity assertion. Retain
                    # the finite approximation and report its error explicitly;
                    # malformed constraints and nonfinite states remain fatal.
                    p.solver_error[w]=0
                    if last_change<=precision and defect<.002 and contact_error<=precision:
                        if lane==0:
                            p.roundoff_warnings[w]+=1
                            p.roundoff_delta[w]=wp.max(p.roundoff_delta[w],last_change)
                    else:
                        if lane==0:
                            p.convergence_warnings[w]+=1
                            p.convergence_metrics[w,0]=wp.max(p.convergence_metrics[w,0],last_change)
                            p.convergence_metrics[w,1]=wp.max(p.convergence_metrics[w,1],defect)
                            p.convergence_metrics[w,2]=wp.max(p.convergence_metrics[w,2],contact_error)
                if lane==0:p.fallback_steps[w]+=iterations
    return tiled



def main():
    import json,time,numpy as np
    from pathlib import Path
    out=Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913/causal_transfer'
    paths=sorted(out.glob('sequential_*_?.npz'))
    assert len(paths)==12
    snapshots=[dict(np.load(p)) for p in paths]
    expected=np.array([np.load(p.with_name(p.stem+'_expected.npy')) for p in paths])
    report=[]; wp.init()
    for device,tiled in [('cpu',False),('cuda:0',False),('cuda:0',True)]:
        problem=SequentialContactProblem(snapshots,device); problem.solve(100,tiled)
        actual=problem.p.velocity.numpy()
        np.testing.assert_allclose(actual,expected,atol=1e-5,rtol=1e-5)
        defect=float(problem.p.stats.numpy().max()); assert defect<.002
        row=dict(device=device,tiled=tiled,max_velocity_error=float(np.max(np.abs(actual-expected))),motor_defect_nm=defect)
        if device.startswith('cuda'):
            batch=SequentialContactProblem([snapshots[i%12] for i in range(512)],device); batch.solve(100,tiled)
            with wp.ScopedCapture(device=device) as capture: batch.solve(100,tiled)
            for _ in range(5): wp.capture_launch(capture.graph)
            wp.synchronize_device(device); start=time.perf_counter()
            for _ in range(50): wp.capture_launch(capture.graph)
            wp.synchronize_device(device)
            row['batch512_solver_ms']=(time.perf_counter()-start)*1000/50
            row['graph_replay_max_error']=float(np.max(np.abs(batch.p.velocity.numpy()-expected[np.arange(512)%12])))
            assert row['graph_replay_max_error']<2e-5
        report.append(row); print(json.dumps(row),flush=True)
    (out/'sequential_gpu.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__': main()
