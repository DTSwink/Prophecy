"""Diagnostic GPU active-set motor elimination; same contact equations.

The original tangent projection metric is retained. This module is not installed
in production and a failed active set is explicit, never silently accepted.
"""
import warp as wp
from sequential_contact_gpu import ContactProblem,multiply,friction_bound


def make_block_iteration(nv,nmotor):
    @wp.kernel(module='unique',enable_backward=False)
    def solve(p:ContactProblem,mass:wp.array3d(dtype=float),identity:wp.array2d(dtype=float),
              iterations:int,error:wp.array(dtype=int)):
        w=wp.tid();dt=p.dt[0]
        # A short scalar solve supplies only the active-set estimate. Momentum
        # still comes from the original free velocity, never this estimate.
        v=wp.tile_load(p.velocity,shape=(1,nv),offset=(w,0),storage='shared')
        guess=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')
        wp.tile_assign(guess,v)
        free_velocity=wp.tile_load(p.free,shape=(1,nv),offset=(w,0))
        M=wp.tile_load(mass[w],shape=(nv,nv),storage='shared')
        momentum=wp.tile_matmul(free_velocity,M)
        eye=wp.tile_load(identity,shape=(nv,nv))
        active=wp.tile_zeros(shape=(1,nmotor),dtype=int,storage='shared')
        for c in range(p.ncontact[w]):
            for a in range(3):p.contact_impulse[w,c,a]=0.
        for c in range(p.nlimit[w]):p.limit_impulse[w,c]=0.
        if p.manifold.enabled:
            for g in range(p.manifold.count[w]):p.manifold.impulse[w,g,2]=0.
        converged=bool(False)
        # Usually one or two branches suffice. Near a torque boundary the
        # damped estimate can need more; retain an explicit bounded failure.
        for outer in range(60):
            effective=wp.tile_zeros(shape=(nv,nv),dtype=float,storage='shared')
            wp.tile_assign(effective,M)
            rhs=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')
            wp.tile_assign(rhs,momentum)
            for a in range(nmotor):
                dof=p.dofs[a];cap=dt*p.caps[a]
                request=dt*p.gains[a]*(p.commands[w,a]-wp.tile_extract(guess,0,dof))
                status=int(0)
                if request>cap:status=1
                elif request< -cap:status=-1
                active[0,a]=status
                if status!=0:rhs[0,dof]=wp.tile_extract(rhs,0,dof)+float(status)*cap
                else:
                    effective[dof,dof]=wp.tile_extract(effective,dof,dof)+dt*p.gains[a]
                    rhs[0,dof]=wp.tile_extract(rhs,0,dof)+dt*p.gains[a]*p.commands[w,a]
            factor=wp.tile_cholesky(effective)
            inverse=wp.tile_cholesky_solve(factor,eye)
            wp.tile_assign(v,wp.tile_matmul(rhs,inverse))
            for c in range(p.ncontact[w]):
                for a in range(3):
                    jac=wp.tile_reshape(wp.tile_load(p.J[w,c,a],shape=(nv,)),shape=(1,nv))
                    response=wp.tile_matmul(jac,inverse)
                    wp.tile_store(p.response[w,c,a],wp.tile_reshape(response,shape=(nv,)))
                    wp.tile_assign(v,v+response*p.contact_impulse[w,c,a])
            for c in range(p.nlimit[w]):
                jac=wp.tile_reshape(wp.tile_load(p.limit_J[w,c],shape=(nv,)),shape=(1,nv))
                response=wp.tile_matmul(jac,inverse)
                wp.tile_store(p.limit_response[w,c],wp.tile_reshape(response,shape=(nv,)))
                wp.tile_assign(v,v+response*p.limit_impulse[w,c])
            if p.manifold.enabled:
                for g in range(p.manifold.count[w]):
                    spin_jac=wp.tile_reshape(wp.tile_load(p.manifold.J[w,g,2],shape=(nv,)),shape=(1,nv))
                    spin_response=wp.tile_matmul(spin_jac,inverse)
                    wp.tile_store(p.manifold.response[w,g,2],wp.tile_reshape(spin_response,shape=(nv,)))
                    wp.tile_assign(v,v+spin_response*p.manifold.impulse[w,g,2])
            for it in range(iterations):
                for c in range(p.nlimit[w]):
                    jac=wp.tile_reshape(wp.tile_load(p.limit_J[w,c],shape=(nv,)),shape=(1,nv))
                    limit_response_iter=wp.tile_reshape(wp.tile_load(p.limit_response[w,c],shape=(nv,)),shape=(1,nv))
                    speed=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jac,v)),0)
                    diagonal=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jac,limit_response_iter)),0)
                    old=p.limit_impulse[w,c];compliance=p.limit_compliance[w,c]
                    value=old+(p.limit_target[w,c]-speed-compliance*old)/(diagonal+compliance)
                    if p.limit_bilateral[w,c]==0:value=wp.max(0.,value)
                    value=old+p.relaxation*(value-old)
                    wp.tile_assign(v,v+limit_response_iter*(value-old));p.limit_impulse[w,c]=value
                for c in range(p.ncontact[w]):
                    if p.friction[w,c]>0.:
                        j1=wp.tile_reshape(wp.tile_load(p.J[w,c,1],shape=(nv,)),shape=(1,nv))
                        j2=wp.tile_reshape(wp.tile_load(p.J[w,c,2],shape=(nv,)),shape=(1,nv))
                        v1=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,j1,v)),0)
                        v2=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,j2,v)),0)
                        old1=p.contact_impulse[w,c,1];old2=p.contact_impulse[w,c,2]
                        t1=old1-v1/p.diagonal[w,c,1];t2=old2-v2/p.diagonal[w,c,2]
                        bounds=friction_bound(p,w,c)
                        length=wp.sqrt(t1*t1+t2*t2);bound=bounds[0]
                        scale=wp.min(1.,bound/wp.max(length,1e-30));t1*=scale;t2*=scale
                        t1=old1+p.relaxation*(t1-old1);t2=old2+p.relaxation*(t2-old2)
                        r1=wp.tile_reshape(wp.tile_load(p.response[w,c,1],shape=(nv,)),shape=(1,nv))
                        r2=wp.tile_reshape(wp.tile_load(p.response[w,c,2],shape=(nv,)),shape=(1,nv))
                        wp.tile_assign(v,v+r1*(t1-old1)+r2*(t2-old2))
                        p.contact_impulse[w,c,1]=t1;p.contact_impulse[w,c,2]=t2
                        if p.manifold.enabled:
                            g=p.manifold.group[w,c]
                            if p.manifold.size[w,g]>1:
                                spin_jac_iter=wp.tile_reshape(wp.tile_load(p.manifold.J[w,g,2],shape=(nv,)),shape=(1,nv))
                                spin_response_iter=wp.tile_reshape(wp.tile_load(p.manifold.response[w,g,2],shape=(nv,)),shape=(1,nv))
                                speed=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,spin_jac_iter,v)),0)
                                oldspin=p.manifold.impulse[w,g,2]
                                spin=wp.clamp(oldspin-speed/p.manifold.diagonal[w,g,2],-bounds[1],bounds[1])
                                spin=oldspin+p.relaxation*(spin-oldspin)
                                wp.tile_assign(v,v+spin_response_iter*(spin-oldspin));p.manifold.impulse[w,g,2]=spin
                    jn=wp.tile_reshape(wp.tile_load(p.J[w,c,0],shape=(nv,)),shape=(1,nv))
                    rn=wp.tile_reshape(wp.tile_load(p.response[w,c,0],shape=(nv,)),shape=(1,nv))
                    vn=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jn,v)),0)
                    diagonal=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jn,rn)),0)
                    old=p.contact_impulse[w,c,0];value=wp.max(0.,old-vn/diagonal)
                    value=old+p.relaxation*(value-old)
                    wp.tile_assign(v,v+rn*(value-old));p.contact_impulse[w,c,0]=value
            changed=bool(False)
            defect=float(0.)
            for a in range(nmotor):
                speed=wp.tile_extract(v,0,p.dofs[a]);cap=dt*p.caps[a]
                request=dt*p.gains[a]*(p.commands[w,a]-speed)
                status=int(0)
                if request>cap:status=1
                elif request< -cap:status=-1
                old_status=wp.tile_extract(active,0,a)
                if status!=old_status:changed=True
                impulse=request
                if old_status!=0:impulse=float(old_status)*cap
                p.motor_impulse[w,a]=impulse
                defect=wp.max(defect,wp.abs(impulse-wp.clamp(request,-cap,cap))/dt)
            p.stats[w,0]=defect
            if not changed:
                converged=True
                break
            # Dampen only the branch-selection estimate. An undamped Newton
            # step can alternate between opposite torque caps forever. The
            # accepted velocity is still the full solution of the original
            # equations, never an average or a damped physical state.
            wp.tile_assign(guess,(guess+v)*.5)
        velocity_out=p.velocity
        wp.tile_store(velocity_out,v,offset=(w,0))
        if not converged and error[w]==0:error[w]=5
    return solve
