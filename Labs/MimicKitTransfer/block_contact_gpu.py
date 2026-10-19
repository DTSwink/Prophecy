"""GPU motor/contact solve with register-resident contact iterations.

The motor equations, contact order and friction fixed point are unchanged.
A common positive scale on BOTH tangent denominators preserves their ratio
and the projected disk's fixed points; spin has the same scalar fixed point.
Full contact corrections replace obsolete under-relaxation. Branch-selection
estimates still use their required 0.5 damping. A velocity-change AND original
row-residual check stops converged sweeps at float32 precision (capped at 1e-4).
The existing 100-sweep ceiling and checked motor fallbacks remain safeguards.
Larger articulations retain the tiled implementation below.
"""
import warp as wp
from sequential_contact_gpu import ContactProblem,multiply,friction_bound


@wp.func_native("""
#if defined(__CUDA_ARCH__)
    for (int delta=16; delta>0; delta/=2)
        value += __shfl_xor_sync(0xffffffff, value, delta);
#endif
    return value;
""")
def warp_sum(value:float)->float: ...

@wp.func_native("""
#if defined(__CUDA_ARCH__)
    __syncwarp();
#endif
    return value;
""")
def warp_barrier(value:float)->float: ...

@wp.func_native("""
#if defined(__CUDA_ARCH__)
    for (int delta=16; delta>0; delta/=2)
        value = fmaxf(value, __shfl_xor_sync(0xffffffff, value, delta));
#endif
    return value;
""")
def warp_max(value:float)->float: ...


def make_block_iteration(nv,nmotor,warm_start=False,retry=False):
    if nv>64:
        return make_tiled_block_iteration(nv,nmotor,warm_start=warm_start,retry=retry)
    # Every caller uses block_dim=32: native reductions cover exactly one warp.
    @wp.kernel(module='unique',enable_backward=False)
    def solve(p:ContactProblem,mass:wp.array3d(dtype=float),identity:wp.array2d(dtype=float),
              iterations:int,error:wp.array(dtype=int)):
        w,lane=wp.tid();dt=p.dt[0]
        warm=bool(False)
        if wp.static(warm_start):
            if wp.static(retry):
                if p.warm_state[w]!=-1:return
            else:
                warm=p.warm_state[w]>0
        # A short scalar solve supplies only the active-set estimate. Momentum
        # still comes from the original free velocity, never this estimate.
        v=wp.tile_load(p.velocity,shape=(1,nv),offset=(w,0),storage='shared')
        guess=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')
        wp.tile_assign(guess,v)
        free_velocity=wp.tile_load(p.free,shape=(1,nv),offset=(w,0))
        # Reuse the mass tile for its effective factor. Keeping separate mass,
        # effective, factor and inverse tiles limits resident worlds on the GPU.
        effective=wp.tile_load(mass[w],shape=(nv,nv),storage='shared')
        momentum=wp.tile_matmul(free_velocity,effective)
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
            wp.tile_assign(effective,wp.tile_load(mass[w],shape=(nv,nv)))
            rhs=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')
            wp.tile_assign(rhs,momentum)
            for a in range(nmotor):
                dof=p.dofs[a];cap=dt*p.caps[a]
                request=dt*p.gains[a]*(p.commands[w,a]-wp.tile_extract(guess,0,dof))
                status=int(0)
                if request>cap:status=1
                elif request< -cap:status=-1
                if warm and outer==0:status=p.warm_status[w,a]
                active[0,a]=status
                if status!=0:rhs[0,dof]=wp.tile_extract(rhs,0,dof)+float(status)*cap
                else:
                    effective[dof,dof]=wp.tile_extract(effective,dof,dof)+dt*p.gains[a]
                    rhs[0,dof]=wp.tile_extract(rhs,0,dof)+dt*p.gains[a]*p.commands[w,a]
            wp.tile_cholesky_inplace(effective)
            # Solve only the RHS vectors used below, without forming an inverse.
            wp.tile_assign(v,wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose(rhs))))
            for c in range(p.ncontact[w]):
                for a in range(3):
                    jac=wp.tile_reshape(wp.tile_load(p.J[w,c,a],shape=(nv,)),shape=(1,nv))
                    response=wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose(jac)))
                    wp.tile_store(p.response[w,c,a],wp.tile_reshape(response,shape=(nv,)))
                    if a==0:
                        p.effective_normal_diagonal[w,c]=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jac,response)),0)
                    wp.tile_assign(v,v+response*p.contact_impulse[w,c,a])
            for c in range(p.nlimit[w]):
                jac=wp.tile_reshape(wp.tile_load(p.limit_J[w,c],shape=(nv,)),shape=(1,nv))
                response=wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose(jac)))
                wp.tile_store(p.limit_response[w,c],wp.tile_reshape(response,shape=(nv,)))
                p.effective_limit_diagonal[w,c]=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jac,response)),0)
                wp.tile_assign(v,v+response*p.limit_impulse[w,c])
            if p.manifold.enabled:
                for g in range(p.manifold.count[w]):
                    spin_jac=wp.tile_reshape(wp.tile_load(p.manifold.J[w,g,2],shape=(nv,)),shape=(1,nv))
                    spin_response=wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose(spin_jac)))
                    wp.tile_store(p.manifold.response[w,g,2],wp.tile_reshape(spin_response,shape=(nv,)))
                    wp.tile_assign(v,v+spin_response*p.manifold.impulse[w,g,2])
            for c in range(p.ncontact[w]):
                if p.friction[w,c]>0.:
                    metric_j1=wp.tile_load(p.J[w,c,1],shape=(nv,))
                    metric_j2=wp.tile_load(p.J[w,c,2],shape=(nv,))
                    metric_r1=wp.tile_load(p.response[w,c,1],shape=(nv,))
                    metric_r2=wp.tile_load(p.response[w,c,2],shape=(nv,))
                    a11=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,metric_j1,metric_r1)),0)
                    a22=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,metric_j2,metric_r2)),0)
                    a12=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,metric_j1,metric_r2)),0)
                    d1=p.diagonal[w,c,1];d2=p.diagonal[w,c,2]
                    b11=a11/d1;b22=a22/d2;b12=a12/wp.sqrt(d1*d2)
                    common=wp.max(1e-6,0.5*(b11+b22+wp.sqrt((b11-b22)*(b11-b22)+4.*b12*b12)))
                    if lane==0:
                        p.block_metric[w,c,0]=d1*common;p.block_metric[w,c,1]=d2*common
            if p.manifold.enabled:
                for g in range(p.manifold.count[w]):
                    metric_js=wp.tile_load(p.manifold.J[w,g,2],shape=(nv,))
                    metric_rs=wp.tile_load(p.manifold.response[w,g,2],shape=(nv,))
                    ds=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,metric_js,metric_rs)),0)
                    if lane==0:p.block_metric[w,g,2]=wp.max(ds,1e-12)
            # Exactly one warp per world. Each lane keeps at most two
            # generalized velocities in registers throughout all sweeps.
            k0=lane;k1=lane+32
            v0=wp.tile_extract(v,0,wp.min(k0,nv-1))
            v1=wp.tile_extract(v,0,wp.min(k1,nv-1))
            if k0>=nv:v0=0.
            if k1>=nv:v1=0.
            v0=warp_barrier(v0)  # Publish the lane-zero preconditioner writes.
            for it in range(iterations):
                before0=v0;before1=v1
                unchanged=bool(True)
                for c in range(p.nlimit[w]):
                    dot=float(0.)
                    if k0<nv:dot+=p.limit_J[w,c,k0]*v0
                    if k1<nv:dot+=p.limit_J[w,c,k1]*v1
                    speed=warp_sum(dot)
                    diagonal=p.effective_limit_diagonal[w,c]
                    old=p.limit_impulse[w,c];compliance=p.limit_compliance[w,c]
                    value=old+(p.limit_target[w,c]-speed-compliance*old)/(diagonal+compliance)
                    if p.limit_bilateral[w,c]==0:value=wp.max(0.,value)
                    value=old+1.0*(value-old)
                    if value!=old:unchanged=False
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
                        t1=old1-speed1/p.block_metric[w,c,0];t2=old2-speed2/p.block_metric[w,c,1]
                        bounds=friction_bound(p,w,c)
                        length=wp.sqrt(t1*t1+t2*t2);bound=bounds[0]
                        scale=wp.min(1.,bound/wp.max(length,1e-30));t1*=scale;t2*=scale
                        t1=old1+1.0*(t1-old1);t2=old2+1.0*(t2-old2)
                        if t1!=old1 or t2!=old2:unchanged=False
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
                                spin=wp.clamp(oldspin-speed/p.block_metric[w,g,2],-bounds[1],bounds[1])
                                spin=oldspin+1.0*(spin-oldspin)
                                if spin!=oldspin:unchanged=False
                                if k0<nv:v0+=p.manifold.response[w,g,2,k0]*(spin-oldspin)
                                if k1<nv:v1+=p.manifold.response[w,g,2,k1]*(spin-oldspin)
                                if lane==0:p.manifold.impulse[w,g,2]=spin
                                v0=warp_barrier(v0)
                    dot=float(0.)
                    if k0<nv:dot+=p.J[w,c,0,k0]*v0
                    if k1<nv:dot+=p.J[w,c,0,k1]*v1
                    vn=warp_sum(dot)
                    diagonal=p.effective_normal_diagonal[w,c]
                    old=p.contact_impulse[w,c,0];value=wp.max(0.,old-vn/diagonal)
                    value=old+1.0*(value-old)
                    if value!=old:unchanged=False
                    if k0<nv:v0+=p.response[w,c,0,k0]*(value-old)
                    if k1<nv:v1+=p.response[w,c,0,k1]*(value-old)
                    if lane==0:p.contact_impulse[w,c,0]=value
                    v0=warp_barrier(v0)
                if unchanged:break
                if it%8==7:
                    change=warp_max(wp.max(wp.abs(v0-before0),wp.abs(v1-before1)))
                    magnitude=warp_max(wp.max(wp.abs(v0),wp.abs(v1)))
                    if change<=wp.min(1e-4,2e-6+9.5367431640625e-7*magnitude):
                        # Absolute plus float32 roundoff bound in the row's
                        # velocity units. This tests original equations, not
                        # just a small net change from cancelling corrections.
                        valid=bool(True)
                        for check_c in range(p.nlimit[w]):
                            check_dot=float(0.);check_scale=float(0.)
                            if k0<nv:
                                term=p.limit_J[w,check_c,k0]*v0;check_dot+=term;check_scale+=wp.abs(term)
                            if k1<nv:
                                term=p.limit_J[w,check_c,k1]*v1;check_dot+=term;check_scale+=wp.abs(term)
                            check_speed=warp_sum(check_dot);norm=warp_sum(check_scale)
                            gap=check_speed+p.limit_compliance[w,check_c]*p.limit_impulse[w,check_c]-p.limit_target[w,check_c]
                            residual=wp.max(0.,-gap)
                            if p.limit_bilateral[w,check_c]!=0 or p.limit_impulse[w,check_c]>0.:residual=wp.abs(gap)
                            if residual>wp.min(1e-4,2e-6+9.5367431640625e-7*norm):valid=False
                        for check_c in range(p.ncontact[w]):
                            check_dot=float(0.);check_scale=float(0.)
                            if k0<nv:
                                term=p.J[w,check_c,0,k0]*v0;check_dot+=term;check_scale+=wp.abs(term)
                            if k1<nv:
                                term=p.J[w,check_c,0,k1]*v1;check_dot+=term;check_scale+=wp.abs(term)
                            check_speed=warp_sum(check_dot);norm=warp_sum(check_scale)
                            residual=wp.max(0.,-check_speed)
                            if p.contact_impulse[w,check_c,0]>0.:residual=wp.abs(check_speed)
                            if residual>wp.min(1e-4,2e-6+9.5367431640625e-7*norm):valid=False
                            if p.friction[w,check_c]>0.:
                                check_dot1=float(0.);check_dot2=float(0.);check_scale=float(0.)
                                if k0<nv:
                                    check_t1=p.J[w,check_c,1,k0]*v0;check_t2=p.J[w,check_c,2,k0]*v0
                                    check_dot1+=check_t1;check_dot2+=check_t2;check_scale+=wp.abs(check_t1)+wp.abs(check_t2)
                                if k1<nv:
                                    check_t1=p.J[w,check_c,1,k1]*v1;check_t2=p.J[w,check_c,2,k1]*v1
                                    check_dot1+=check_t1;check_dot2+=check_t2;check_scale+=wp.abs(check_t1)+wp.abs(check_t2)
                                check_speed1=warp_sum(check_dot1);check_speed2=warp_sum(check_dot2);norm=warp_sum(check_scale)
                                check_old1=p.contact_impulse[w,check_c,1];check_old2=p.contact_impulse[w,check_c,2]
                                check_t1=check_old1-check_speed1/p.diagonal[w,check_c,1];check_t2=check_old2-check_speed2/p.diagonal[w,check_c,2]
                                check_bounds=friction_bound(p,w,check_c);check_length=wp.sqrt(check_t1*check_t1+check_t2*check_t2)
                                ratio=wp.min(1.,check_bounds[0]/wp.max(check_length,1e-30))
                                residual=wp.max(wp.abs(check_t1*ratio-check_old1)*p.diagonal[w,check_c,1],wp.abs(check_t2*ratio-check_old2)*p.diagonal[w,check_c,2])
                                if residual>wp.min(1e-4,2e-6+9.5367431640625e-7*norm):valid=False
                                if p.manifold.enabled:
                                    check_g=p.manifold.group[w,check_c]
                                    if p.manifold.size[w,check_g]>1:
                                        check_dot=float(0.);check_scale=float(0.)
                                        if k0<nv:
                                            term=p.manifold.J[w,check_g,2,k0]*v0;check_dot+=term;check_scale+=wp.abs(term)
                                        if k1<nv:
                                            term=p.manifold.J[w,check_g,2,k1]*v1;check_dot+=term;check_scale+=wp.abs(term)
                                        check_speed=warp_sum(check_dot);norm=warp_sum(check_scale)
                                        check_old=p.manifold.impulse[w,check_g,2]
                                        expected=wp.clamp(check_old-check_speed/p.manifold.diagonal[w,check_g,2],-check_bounds[1],check_bounds[1])
                                        residual=wp.abs(expected-check_old)*p.manifold.diagonal[w,check_g,2]
                                        if residual>wp.min(1e-4,2e-6+9.5367431640625e-7*norm):valid=False
                        if valid:break

            if k0<nv:p.velocity[w,k0]=v0
            if k1<nv:p.velocity[w,k1]=v1
            v0=warp_barrier(v0)
            wp.tile_assign(v,wp.tile_load(p.velocity,shape=(1,nv),offset=(w,0)))
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
            if warm:
                # Reject the guess, then perform the unchanged full seed/solve.
                if lane==0:p.warm_state[w]=-1
                return
            # Dampen only the branch-selection estimate. An undamped Newton
            # step can alternate between opposite torque caps forever. The
            # accepted velocity is still the full solution of the original
            # equations, never an average or a damped physical state.
            wp.tile_assign(guess,(guess+v)*.5)
        if wp.static(warm_start):
            if lane==0:p.warm_state[w]=int(converged)
            if converged:
                for a in range(nmotor):
                    status=wp.tile_extract(active,0,a)
                    if lane==0:p.warm_status[w,a]=status
        velocity_out=p.velocity
        wp.tile_store(velocity_out,v,offset=(w,0))
        if not converged and error[w]==0:error[w]=5
    return solve


# Compatibility path for articulations exceeding two coordinates per lane.
def make_tiled_block_iteration(nv,nmotor,warm_start=False,retry=False):
    @wp.kernel(module='unique',enable_backward=False)
    def solve(p:ContactProblem,mass:wp.array3d(dtype=float),identity:wp.array2d(dtype=float),
              iterations:int,error:wp.array(dtype=int)):
        w,lane=wp.tid();dt=p.dt[0]
        warm=bool(False)
        if wp.static(warm_start):
            if wp.static(retry):
                if p.warm_state[w]!=-1:return
            else:
                warm=p.warm_state[w]>0
        # A short scalar solve supplies only the active-set estimate. Momentum
        # still comes from the original free velocity, never this estimate.
        v=wp.tile_load(p.velocity,shape=(1,nv),offset=(w,0),storage='shared')
        guess=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')
        wp.tile_assign(guess,v)
        free_velocity=wp.tile_load(p.free,shape=(1,nv),offset=(w,0))
        # Reuse the mass tile for its effective factor. Keeping separate mass,
        # effective, factor and inverse tiles limits resident worlds on the GPU.
        effective=wp.tile_load(mass[w],shape=(nv,nv),storage='shared')
        momentum=wp.tile_matmul(free_velocity,effective)
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
            wp.tile_assign(effective,wp.tile_load(mass[w],shape=(nv,nv)))
            rhs=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')
            wp.tile_assign(rhs,momentum)
            for a in range(nmotor):
                dof=p.dofs[a];cap=dt*p.caps[a]
                request=dt*p.gains[a]*(p.commands[w,a]-wp.tile_extract(guess,0,dof))
                status=int(0)
                if request>cap:status=1
                elif request< -cap:status=-1
                if warm and outer==0:status=p.warm_status[w,a]
                active[0,a]=status
                if status!=0:rhs[0,dof]=wp.tile_extract(rhs,0,dof)+float(status)*cap
                else:
                    effective[dof,dof]=wp.tile_extract(effective,dof,dof)+dt*p.gains[a]
                    rhs[0,dof]=wp.tile_extract(rhs,0,dof)+dt*p.gains[a]*p.commands[w,a]
            wp.tile_cholesky_inplace(effective)
            # Solve only the RHS vectors used below, without forming an inverse.
            wp.tile_assign(v,wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose(rhs))))
            for c in range(p.ncontact[w]):
                for a in range(3):
                    jac=wp.tile_reshape(wp.tile_load(p.J[w,c,a],shape=(nv,)),shape=(1,nv))
                    response=wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose(jac)))
                    wp.tile_store(p.response[w,c,a],wp.tile_reshape(response,shape=(nv,)))
                    if a==0:
                        p.effective_normal_diagonal[w,c]=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jac,response)),0)
                    wp.tile_assign(v,v+response*p.contact_impulse[w,c,a])
            for c in range(p.nlimit[w]):
                jac=wp.tile_reshape(wp.tile_load(p.limit_J[w,c],shape=(nv,)),shape=(1,nv))
                response=wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose(jac)))
                wp.tile_store(p.limit_response[w,c],wp.tile_reshape(response,shape=(nv,)))
                p.effective_limit_diagonal[w,c]=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jac,response)),0)
                wp.tile_assign(v,v+response*p.limit_impulse[w,c])
            if p.manifold.enabled:
                for g in range(p.manifold.count[w]):
                    spin_jac=wp.tile_reshape(wp.tile_load(p.manifold.J[w,g,2],shape=(nv,)),shape=(1,nv))
                    spin_response=wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose(spin_jac)))
                    wp.tile_store(p.manifold.response[w,g,2],wp.tile_reshape(spin_response,shape=(nv,)))
                    wp.tile_assign(v,v+spin_response*p.manifold.impulse[w,g,2])
            for it in range(iterations):
                unchanged=bool(True)
                for c in range(p.nlimit[w]):
                    jac=wp.tile_reshape(wp.tile_load(p.limit_J[w,c],shape=(nv,)),shape=(1,nv))
                    limit_response_iter=wp.tile_reshape(wp.tile_load(p.limit_response[w,c],shape=(nv,)),shape=(1,nv))
                    speed=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jac,v)),0)
                    diagonal=p.effective_limit_diagonal[w,c]
                    old=p.limit_impulse[w,c];compliance=p.limit_compliance[w,c]
                    value=old+(p.limit_target[w,c]-speed-compliance*old)/(diagonal+compliance)
                    if p.limit_bilateral[w,c]==0:value=wp.max(0.,value)
                    value=old+p.relaxation*(value-old)
                    if value!=old:unchanged=False
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
                        if t1!=old1 or t2!=old2:unchanged=False
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
                                if spin!=oldspin:unchanged=False
                                wp.tile_assign(v,v+spin_response_iter*(spin-oldspin));p.manifold.impulse[w,g,2]=spin
                    jn=wp.tile_reshape(wp.tile_load(p.J[w,c,0],shape=(nv,)),shape=(1,nv))
                    rn=wp.tile_reshape(wp.tile_load(p.response[w,c,0],shape=(nv,)),shape=(1,nv))
                    vn=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jn,v)),0)
                    diagonal=p.effective_normal_diagonal[w,c]
                    old=p.contact_impulse[w,c,0];value=wp.max(0.,old-vn/diagonal)
                    value=old+p.relaxation*(value-old)
                    if value!=old:unchanged=False
                    wp.tile_assign(v,v+rn*(value-old));p.contact_impulse[w,c,0]=value
                # No changed impulse means an exact fixed point. Further
                # identical sweeps cannot alter it; no relaxed tolerance.
                if unchanged:break
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
            if warm:
                # Reject the guess, then perform the unchanged full seed/solve.
                if lane==0:p.warm_state[w]=-1
                return
            # Dampen only the branch-selection estimate. An undamped Newton
            # step can alternate between opposite torque caps forever. The
            # accepted velocity is still the full solution of the original
            # equations, never an average or a damped physical state.
            wp.tile_assign(guess,(guess+v)*.5)
        if wp.static(warm_start):
            if lane==0:p.warm_state[w]=int(converged)
            if converged:
                for a in range(nmotor):
                    status=wp.tile_extract(active,0,a)
                    if lane==0:p.warm_status[w,a]=status
        velocity_out=p.velocity
        wp.tile_store(velocity_out,v,offset=(w,0))
        if not converged and error[w]==0:error[w]=5
    return solve
