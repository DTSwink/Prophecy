"""Rare coupled motor/contact solve after the block branch iteration fails.

Solve the existing impulse fixed point x = project(x + (target - Jv - Cx)/D),
with v = v_free + M^-1 J^T x. Projections retain capped motors, unilateral
normals/limits, the existing friction disks and manifold spin bounds. No changed
physics parameters. A safeguarded semismooth Newton step resolves simultaneous
motor/friction branch changes that make separate branch guesses cycle.

Each failed attempt is discarded; an independent relaxed scalar seed advances
16 sweeps before the next attempt (at most eight). Partial-pivot LU and residual
line search reject singular/stalled steps. Only a finite converged root commits
outputs. Otherwise error5 is retained for the existing checked scalar fallback.
Other error codes are never cleared. Ordinary block solves are untouched.

Scratch is allocated once for16 parallel worlds, reused in a captured CUDA graph.
All arithmetic here is float64; the original engine output remains float32.
"""
import warp as wp
from sequential_contact_gpu import ContactProblem

@wp.struct
class Problem:
    n: int
    base: wp.array2d(dtype=wp.float64)
    response: wp.array3d(dtype=wp.float64)
    family: wp.array2d(dtype=int)
    index: wp.array2d(dtype=int)
    B: wp.array3d(dtype=wp.float64)
    b: wp.array2d(dtype=wp.float64)
    scale: wp.array2d(dtype=wp.float64)
    compliance: wp.array2d(dtype=wp.float64)
    target: wp.array2d(dtype=wp.float64)
    bound: wp.array2d(dtype=wp.float64)
    bound_derivative: wp.array3d(dtype=wp.float64)
    kind: wp.array2d(dtype=int)
    x: wp.array2d(dtype=wp.float64)
    trial: wp.array2d(dtype=wp.float64)
    q: wp.array2d(dtype=wp.float64)
    r: wp.array2d(dtype=wp.float64)
    jac: wp.array3d(dtype=wp.float64)
    rhs: wp.array2d(dtype=wp.float64)
    direction: wp.array2d(dtype=wp.float64)
    result: wp.array2d(dtype=wp.float64)

@wp.func
def dq(p:Problem,w:int,i:int,j:int):
    delta=wp.float64(0.)
    if i==j:delta=wp.float64(1.)-p.compliance[w,i]/p.scale[w,i]
    return delta-p.B[w,i,j]/p.scale[w,i]

@wp.func_native('''
#if defined(__CUDA_ARCH__)
__syncthreads();
#endif
''')
def synchronize_block():
    ...

@wp.func
def coefficient(q:ContactProblem,w:int,family:int,index:int,j:int):
    v=wp.float64(0.)
    if family==0:
        if j==q.dofs[index]:v=wp.float64(1.)
    elif family==1:v=wp.float64(q.limit_J[w,index,j])
    elif family==2:v=wp.float64(q.J[w,index,0,j])
    elif family==3:v=wp.float64(q.J[w,index,1,j])
    elif family==4:v=wp.float64(q.J[w,index,2,j])
    elif family==5:v=wp.float64(q.manifold.J[w,index,2,j])
    return v

@wp.func
def row(q:ContactProblem,w:int,p:Problem,s:int,lane:int,r:int,family:int,index:int,kind:int):
    if lane==0:
        p.family[s,r]=family;p.index[s,r]=index;p.kind[s,r]=kind

@wp.func
def prepare(q:ContactProblem,w:int,p:Problem,s:int,lane:int):
    r=int(0)
    for a in range(q.nmotor):row(q,w,p,s,lane,r,0,a,0);r+=1
    for a in range(q.nlimit[w]):
        kind=int(1)
        if q.limit_bilateral[w,a]!=0:kind=5
        row(q,w,p,s,lane,r,1,a,kind);r+=1
    for c in range(q.ncontact[w]):
        if q.friction[w,c]>0.:
            row(q,w,p,s,lane,r,3,c,2);r+=1
            row(q,w,p,s,lane,r,4,c,3);r+=1
            if q.manifold.enabled:
                g=q.manifold.group[w,c]
                if q.manifold.size[w,g]>1:
                    row(q,w,p,s,lane,r,5,g,4);r+=1
        row(q,w,p,s,lane,r,2,c,1);r+=1
    synchronize_block()
    for i in range(lane,r,wp.block_dim()):
        family=p.family[s,i];index=p.index[s,i]
        for j in range(q.nv):
            value=wp.float64(0.)
            for k in range(q.nv):value+=wp.float64(q.inv[w,j,k])*coefficient(q,w,family,index,k)
            p.response[s,i,j]=value
        free=wp.float64(0.)
        for j in range(q.nv):free+=coefficient(q,w,family,index,j)*wp.float64(q.free[w,j])
        p.b[s,i]=free;p.base[s,i]=wp.float64(0.)
        p.bound[s,i]=wp.float64(0.);p.target[s,i]=wp.float64(0.);p.compliance[s,i]=wp.float64(0.)
        if family==0:
            p.bound[s,i]=wp.float64(q.dt[0])*wp.float64(q.caps[index])
            p.compliance[s,i]=wp.float64(1.)/(wp.float64(q.dt[0])*wp.float64(q.gains[index]))
            p.target[s,i]=wp.float64(q.commands[w,index])
        elif family==1:
            p.target[s,i]=wp.float64(q.limit_target[w,index]);p.compliance[s,i]=wp.float64(q.limit_compliance[w,index])
    synchronize_block()
    for i in range(lane,r,wp.block_dim()):
        family=p.family[s,i];index=p.index[s,i]
        for j in range(r):
            value=wp.float64(0.)
            for k in range(q.nv):value+=coefficient(q,w,family,index,k)*p.response[s,j,k]
            p.B[s,i,j]=value
            bound=wp.float64(0.)
            if p.family[s,j]==2 and (family==3 or family==4 or family==5):
                c=p.index[s,j]
                if family==5:
                    if q.manifold.group[w,c]==index:
                        # The manifold lead owns its friction coefficient.
                        mu=wp.float64(0.)
                        for lead in range(q.ncontact[w]):
                            if q.manifold.group[w,lead]==index:mu=wp.max(mu,wp.float64(q.friction[w,lead]))
                        bound=mu*wp.float64(q.manifold.radius[w,c])
                elif q.manifold.enabled:
                    if q.manifold.group[w,c]==q.manifold.group[w,index]:bound=wp.float64(q.friction[w,index])
                elif c==index:bound=wp.float64(q.friction[w,index])
            p.bound_derivative[s,i,j]=bound
        p.scale[s,i]=p.B[s,i,i]+p.compliance[s,i]
        if family==3:p.scale[s,i]=wp.float64(q.diagonal[w,index,1])
        elif family==4:p.scale[s,i]=wp.float64(q.diagonal[w,index,2])
        elif family==5:p.scale[s,i]=wp.float64(q.manifold.diagonal[w,index,2])
    synchronize_block()
    return r

@wp.func
def seed_q(p:Problem,s:int,i:int):
    speed=p.b[s,i];bound=p.bound[s,i]
    for j in range(p.n):
        speed+=p.B[s,i,j]*p.base[s,j]
        bound+=p.bound_derivative[s,i,j]*p.base[s,j]
    value=p.base[s,i]+(p.target[s,i]-speed-p.compliance[s,i]*p.base[s,i])/p.scale[s,i]
    return wp.vec2d(value,wp.max(wp.float64(0.),bound))

@wp.func
def advance_seed(p:Problem,s:int,steps:int):
    for iteration in range(steps):
        for i in range(p.n):
            kind=p.kind[s,i]
            if kind==3:continue
            pair=seed_q(p,s,i);value=pair[0];bound=pair[1]
            if kind==0 or kind==4:value=wp.clamp(value,-bound,bound)
            elif kind==1:value=wp.max(wp.float64(0.),value)
            elif kind==2:
                other=seed_q(p,s,i+1)[0];length=wp.sqrt(value*value+other*other)
                scale=wp.min(wp.float64(1.),bound/wp.max(length,wp.float64(1e-30)))
                value*=scale;p.base[s,i+1]=(p.base[s,i+1]+other*scale)*wp.float64(.5)
            p.base[s,i]=(p.base[s,i]+value)*wp.float64(.5)

@wp.func
def accept(q:ContactProblem,w:int,p:Problem,s:int,lane:int):
    for j in range(lane,q.nv,wp.block_dim()):
        v=wp.float64(q.free[w,j])
        for i in range(p.n):v+=p.response[s,i,j]*p.x[s,i]
        q.velocity[w,j]=float(v)
    for c in range(lane,q.ncontact[w],wp.block_dim()):
        for a in range(3):q.contact_impulse[w,c,a]=0.
    synchronize_block()
    for i in range(lane,p.n,wp.block_dim()):
        f=p.family[s,i];index=p.index[s,i];value=float(p.x[s,i])
        if f==0:q.motor_impulse[w,index]=value
        elif f==1:q.limit_impulse[w,index]=value
        elif f==2:q.contact_impulse[w,index,0]=value
        elif f==3:q.contact_impulse[w,index,1]=value
        elif f==4:q.contact_impulse[w,index,2]=value
        elif f==5:q.manifold.impulse[w,index,2]=value
    synchronize_block()
    if lane==0:
        defect=float(0.)
        for a in range(q.nmotor):
            expected=wp.clamp(q.gains[a]*(q.commands[w,a]-q.velocity[w,q.dofs[a]]),-q.caps[a],q.caps[a])
            defect=wp.max(defect,wp.abs(q.motor_impulse[w,a]/q.dt[0]-expected))
        q.stats[w,0]=defect;q.solver_error[w]=0;q.warm_state[w]=0

@wp.func
def qrow(i:int,p:Problem,w:int,trial:bool):
    value=wp.float64(0.)
    if i<p.n:
        x=p.x[w,i]
        if trial:x=p.trial[w,i]
        speed=p.b[w,i]
        for j in range(p.n):
            xx=p.x[w,j]
            if trial:xx=p.trial[w,j]
            speed+=p.B[w,i,j]*xx
        value=x+(p.target[w,i]-speed-p.compliance[w,i]*x)/p.scale[w,i]
    return value

@wp.func
def rrow(i:int,p:Problem,w:int,trial:bool,derivative:bool):
    residual=wp.float64(0.)
    if i<p.n:
        x=p.x[w,i]
        if trial:x=p.trial[w,i]
        kind=p.kind[w,i];q=p.q[w,i];bound=p.bound[w,i]
        for j in range(p.n):
            xx=p.x[w,j]
            if trial:xx=p.trial[w,j]
            bound+=p.bound_derivative[w,i,j]*xx
        raw_bound=bound
        db_enabled=bound>wp.float64(0.)
        bound=wp.max(wp.float64(0.),bound)
        value=wp.float64(0.);pd=wp.float64(0.);bd=wp.float64(0.)
        tangent=int(-1);length=wp.float64(0.)
        if kind==0 or kind==4:
            value=wp.clamp(q,-bound,bound)
            if q>bound:bd=wp.float64(1.)
            elif q<-bound:bd=wp.float64(-1.)
            else:pd=wp.float64(1.)
        elif kind==1:
            value=wp.max(wp.float64(0.),q)
            if q>wp.float64(0.):pd=wp.float64(1.)
        elif kind==5:
            value=q;pd=wp.float64(1.)
        else:
            tangent=i+1
            if kind==3:tangent=i-1
            other=p.q[w,tangent];length=wp.sqrt(q*q+other*other)
            if length<=bound:value=q;pd=wp.float64(1.)
            elif length>wp.float64(0.):value=bound*q/length;bd=q/length
        residual=x-value
        # CUDA min/max projections can mask NaNs. Preserve invalid inputs in
        # the residual so they cannot be accepted as a converged root.
        if not (wp.isfinite(q) and wp.isfinite(raw_bound)):
            residual=q+raw_bound
        if derivative:
            for j in range(p.n):
                jac=wp.float64(0.)
                if i==j:jac=wp.float64(1.)
                jac-=pd*dq(p,w,i,j)
                if db_enabled:jac-=bd*p.bound_derivative[w,i,j]
                if tangent>=0 and length>bound and length>wp.float64(0.):
                    a=q/length;b=p.q[w,tangent]/length
                    jac-=bound/length*((wp.float64(1.)-a*a)*dq(p,w,i,j)-a*b*dq(p,w,tangent,j))
                p.jac[w,i,j]=jac
    return residual

@wp.func
def square(x:wp.float64):return x*x
@wp.func
def product(x:wp.float64,y:wp.float64):return x*y
@wp.func
def absolute(x:wp.float64):return wp.abs(x)
@wp.func
def evaluate_parallel(p:Problem,w:int,lane:int,trial:bool,derivative:bool):
    for i in range(lane,p.n,wp.block_dim()):p.q[w,i]=qrow(i,p,w,trial)
    synchronize_block()
    for i in range(lane,p.n,wp.block_dim()):p.r[w,i]=rrow(i,p,w,trial,derivative)
    synchronize_block()


def make_candidate(n,slots):
    @wp.kernel(module='unique',enable_backward=False)
    def solve(q:ContactProblem,p:Problem,nworld:int):
        w,lane=wp.tid()
        x_out=p.x;trial_out=p.trial;direction_out=p.direction
        direction=wp.tile_zeros(shape=(1,n),dtype=wp.float64,storage='shared')
        for world in range(w,nworld,slots):
            if q.solver_error[world]!=5:continue
            p.n=prepare(q,world,p,w,lane)
            for i in range(lane,n,wp.block_dim()):
                p.x[w,i]=wp.float64(0.);p.r[w,i]=wp.float64(0.);p.trial[w,i]=wp.float64(0.)
            synchronize_block()
            total=int(0);seed=int(0);err=wp.float64(1.)
            for attempt in range(8):
                if lane==0:advance_seed(p,w,16)
                synchronize_block()
                for i in range(lane,p.n,wp.block_dim()):p.x[w,i]=p.base[w,i]
                synchronize_block()
                failure=int(0);count=int(0);seed+=16
                for iteration in range(12):
                    count=iteration+1
                    evaluate_parallel(p,w,lane,False,True)
                    residual=wp.tile_load(p.r[w],shape=(n,))
                    err=wp.tile_extract(wp.tile_max(wp.tile_map(absolute,residual)),0)
                    norm=wp.tile_extract(wp.tile_sum(wp.tile_map(square,residual)),0)
                    if wp.isfinite(norm) and err<wp.float64(1e-10):break
                    for i in range(lane,p.n,wp.block_dim()):p.rhs[w,i]=-p.r[w,i]
                    synchronize_block()
                    for k in range(p.n):
                        for i in range(lane,n,wp.block_dim()):
                            value=wp.float64(-1.)
                            if i>=k and i<p.n:value=wp.abs(p.jac[w,i,k])
                            p.direction[w,i]=value
                        synchronize_block()
                        candidates=wp.tile_load(p.direction[w],shape=(n,))
                        pivot=wp.tile_extract(wp.tile_argmax(candidates),0)
                        maxv=wp.tile_extract(candidates,pivot)
                        if maxv<wp.float64(1e-12):failure=1;break
                        if pivot!=k:
                            for j in range(lane,p.n,wp.block_dim()):
                                saved=p.jac[w,k,j];p.jac[w,k,j]=p.jac[w,pivot,j];p.jac[w,pivot,j]=saved
                            if lane==0:
                                rv=p.rhs[w,k];p.rhs[w,k]=p.rhs[w,pivot];p.rhs[w,pivot]=rv
                        synchronize_block()
                        for i in range(k+1+lane,p.n,wp.block_dim()):
                            factor=p.jac[w,i,k]/p.jac[w,k,k]
                            for j in range(k+1,p.n):p.jac[w,i,j]-=factor*p.jac[w,k,j]
                            p.jac[w,i,k]=wp.float64(0.)
                            p.rhs[w,i]-=factor*p.rhs[w,k]
                        synchronize_block()
                    if failure!=0:break
                    wp.tile_assign(direction,wp.tile_zeros(shape=(1,n),dtype=wp.float64))
                    for back in range(p.n):
                        i=p.n-back-1
                        backrow=wp.tile_load(p.jac[w],shape=(1,n),offset=(i,0))
                        dot=wp.tile_extract(wp.tile_sum(wp.tile_map(product,backrow,direction)),0)
                        direction[0,i]=(p.rhs[w,i]-dot)/p.jac[w,i,i]
                    wp.tile_store(direction_out,direction,offset=(w,0))
                    x=wp.tile_load(p.x,shape=(1,n),offset=(w,0))
                    alpha=wp.float64(1.);accepted=bool(False)
                    for line in range(12):
                        wp.tile_store(trial_out,x+direction*alpha,offset=(w,0))
                        synchronize_block()
                        evaluate_parallel(p,w,lane,True,False)
                        rr=wp.tile_load(p.r[w],shape=(n,))
                        trialnorm=wp.tile_extract(wp.tile_sum(wp.tile_map(square,rr)),0)
                        if trialnorm<norm*(wp.float64(1.)-wp.float64(1e-4)*alpha):accepted=True;break
                        alpha*=wp.float64(.5)
                    if not accepted:failure=2;break
                    wp.tile_store(x_out,x+direction*alpha,offset=(w,0))
                    synchronize_block()
                evaluate_parallel(p,w,lane,False,False)
                rr=wp.tile_load(p.r[w],shape=(n,))
                err=wp.tile_extract(wp.tile_max(wp.tile_map(absolute,rr)),0)
                final_norm=wp.tile_extract(wp.tile_sum(wp.tile_map(square,rr)),0)
                total+=count
                if wp.isfinite(final_norm) and err<wp.float64(1e-10):
                    accept(q,world,p,w,lane)
                    break
            if lane==0:
                p.result[world,0]=wp.float64(total);p.result[world,1]=err;p.result[world,2]=wp.float64(seed)
                p.result[world,3]+=wp.float64(1.);p.result[world,4]+=wp.float64(total);p.result[world,5]+=wp.float64(seed)
    return solve


def allocate(q,slots=16):
    n=q.nmotor+4*q.J.shape[1]+q.limit_J.shape[1];slots=min(slots,q.free.shape[0]);dev=q.free.device
    p=Problem();p.n=0
    z=lambda shape:wp.zeros(shape,dtype=wp.float64,device=dev)
    for name in ('B','bound_derivative','jac'):setattr(p,name,z((slots,n,n)))
    for name in ('b','scale','compliance','target','bound','x','trial','q','r','rhs','direction','base'):setattr(p,name,z((slots,n)))
    for name in ('kind','family','index'):setattr(p,name,wp.zeros((slots,n),dtype=int,device=dev))
    p.response=z((slots,n,q.nv));p.result=z((q.free.shape[0],6))
    return p,make_candidate(n,slots),slots
