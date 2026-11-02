"""Register-resident finite-budget sequential impulses for recovery fine-tuning.

Same row order and relaxation as the original scalar solver; float32 reduction
order differs. A bounded solve is approximate, unlike the converged block profile.
"""
import warp as wp
from sequential_contact_gpu import ContactProblem,friction_bound
from block_contact_gpu import warp_sum,warp_barrier

def make_iteration(nv):
    assert nv<=64
    @wp.kernel(module='unique',enable_backward=False)
    def solve(p:ContactProblem,iterations:int):
        w,lane=wp.tid();dt=p.dt[0];k0=lane;k1=lane+32
        v0=float(0.);v1=float(0.)
        if k0<nv:v0=p.free[w,k0]
        if k1<nv:v1=p.free[w,k1]
        for a in range(lane,p.nmotor,32):p.motor_impulse[w,a]=0.
        for c in range(lane,p.ncontact[w],32):
            for a in range(3):p.contact_impulse[w,c,a]=0.
        for c in range(lane,p.nlimit[w],32):p.limit_impulse[w,c]=0.
        if p.manifold.enabled:
            for g in range(lane,p.manifold.count[w],32):p.manifold.impulse[w,g,2]=0.
        v0=warp_barrier(v0)
        for it in range(iterations):
            for a in range(p.nmotor):
                dof=p.dofs[a];old=p.motor_impulse[w,a]
                speed=float(0.)
                if dof==k0:speed=v0
                if dof==k1:speed=v1
                speed=warp_sum(speed)
                compliance=1./(dt*p.gains[a]);cap=dt*p.caps[a]
                impulse=wp.clamp(old+(p.commands[w,a]-speed-compliance*old)/(p.inv[w,dof,dof]+compliance),-cap,cap)
                impulse=old+p.relaxation*(impulse-old)
                if k0<nv:v0+=p.inv[w,dof,k0]*(impulse-old)
                if k1<nv:v1+=p.inv[w,dof,k1]*(impulse-old)
                if lane==0:p.motor_impulse[w,a]=impulse
                v0=warp_barrier(v0)
            for c in range(p.nlimit[w]):
                dot=float(0.)
                if k0<nv:dot+=p.limit_J[w,c,k0]*v0
                if k1<nv:dot+=p.limit_J[w,c,k1]*v1
                speed=warp_sum(dot)
                diagonal=p.limit_diagonal[w,c]
                old=p.limit_impulse[w,c];compliance=p.limit_compliance[w,c]
                value=old+(p.limit_target[w,c]-speed-compliance*old)/(diagonal+compliance)
                if p.limit_bilateral[w,c]==0:value=wp.max(0.,value)
                value=old+p.relaxation*(value-old)
                if k0<nv:v0+=p.limit_response[w,c,k0]*(value-old)
                if k1<nv:v1+=p.limit_response[w,c,k1]*(value-old)
                if lane==0:p.limit_impulse[w,c]=value
                v0=warp_barrier(v0)
            for c in range(p.ncontact[w]):
                if p.friction[w,c]>0.:
                    dot1=float(0.);dot2=float(0.)
                    if k0<nv:
                        dot1+=p.J[w,c,1,k0]*v0;dot2+=p.J[w,c,2,k0]*v0
                    if k1<nv:
                        dot1+=p.J[w,c,1,k1]*v1;dot2+=p.J[w,c,2,k1]*v1
                    speed1=warp_sum(dot1);speed2=warp_sum(dot2)
                    old1=p.contact_impulse[w,c,1];old2=p.contact_impulse[w,c,2]
                    t1=old1-speed1/p.diagonal[w,c,1];t2=old2-speed2/p.diagonal[w,c,2]
                    bounds=friction_bound(p,w,c)
                    length=wp.sqrt(t1*t1+t2*t2);bound=bounds[0]
                    scale=wp.min(1.,bound/wp.max(length,1e-30));t1*=scale;t2*=scale
                    t1=old1+p.relaxation*(t1-old1);t2=old2+p.relaxation*(t2-old2)
                    if k0<nv:v0+=p.response[w,c,1,k0]*(t1-old1)+p.response[w,c,2,k0]*(t2-old2)
                    if k1<nv:v1+=p.response[w,c,1,k1]*(t1-old1)+p.response[w,c,2,k1]*(t2-old2)
                    if lane==0:
                        p.contact_impulse[w,c,1]=t1;p.contact_impulse[w,c,2]=t2
                    v0=warp_barrier(v0)
                    if p.manifold.enabled:
                        g=p.manifold.group[w,c]
                        if p.manifold.size[w,g]>1:
                            dot=float(0.)
                            if k0<nv:dot+=p.manifold.J[w,g,2,k0]*v0
                            if k1<nv:dot+=p.manifold.J[w,g,2,k1]*v1
                            speed=warp_sum(dot)
                            oldspin=p.manifold.impulse[w,g,2]
                            spin=wp.clamp(oldspin-speed/p.manifold.diagonal[w,g,2],-bounds[1],bounds[1])
                            spin=oldspin+p.relaxation*(spin-oldspin)
                            if k0<nv:v0+=p.manifold.response[w,g,2,k0]*(spin-oldspin)
                            if k1<nv:v1+=p.manifold.response[w,g,2,k1]*(spin-oldspin)
                            if lane==0:p.manifold.impulse[w,g,2]=spin
                            v0=warp_barrier(v0)
                dot=float(0.)
                if k0<nv:dot+=p.J[w,c,0,k0]*v0
                if k1<nv:dot+=p.J[w,c,0,k1]*v1
                vn=warp_sum(dot)
                diagonal=p.diagonal[w,c,0]
                old=p.contact_impulse[w,c,0];value=wp.max(0.,old-vn/diagonal)
                value=old+p.relaxation*(value-old)
                if k0<nv:v0+=p.response[w,c,0,k0]*(value-old)
                if k1<nv:v1+=p.response[w,c,0,k1]*(value-old)
                if lane==0:p.contact_impulse[w,c,0]=value
                v0=warp_barrier(v0)
        if k0<nv:p.velocity[w,k0]=v0
        if k1<nv:p.velocity[w,k1]=v1
        defect=float(0.)
        for a in range(p.nmotor):
            dof=p.dofs[a];speed=float(0.)
            if dof==k0:speed=v0
            if dof==k1:speed=v1
            speed=warp_sum(speed)
            expected=wp.clamp(p.gains[a]*(p.commands[w,a]-speed),-p.caps[a],p.caps[a])
            defect=wp.max(defect,wp.abs(p.motor_impulse[w,a]/dt-expected))
        if lane==0:p.stats[w,0]=defect
        if not wp.isfinite(v0) or not wp.isfinite(v1) or not wp.isfinite(defect):
            p.solver_error[w]=4
    return solve
