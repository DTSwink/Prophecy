"""Disposable register-resident contact sweep, preserving update order/law."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

NATIVE='''
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

'''

LOOP='''            # Exactly one warp per world. Each lane keeps at most two
            # generalized velocities in registers throughout all sweeps.
            k0=lane;k1=lane+32
            v0=wp.tile_extract(v,0,wp.min(k0,nv-1))
            v1=wp.tile_extract(v,0,wp.min(k1,nv-1))
            if k0>=nv:v0=0.
            if k1>=nv:v1=0.
            for it in range(iterations):
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
                    value=old+p.relaxation*(value-old)
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
                        t1=old1-speed1/p.diagonal[w,c,1];t2=old2-speed2/p.diagonal[w,c,2]
                        bounds=friction_bound(p,w,c)
                        length=wp.sqrt(t1*t1+t2*t2);bound=bounds[0]
                        scale=wp.min(1.,bound/wp.max(length,1e-30));t1*=scale;t2*=scale
                        t1=old1+p.relaxation*(t1-old1);t2=old2+p.relaxation*(t2-old2)
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
                                spin=wp.clamp(oldspin-speed/p.manifold.diagonal[w,g,2],-bounds[1],bounds[1])
                                spin=oldspin+p.relaxation*(spin-oldspin)
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
                    value=old+p.relaxation*(value-old)
                    if value!=old:unchanged=False
                    if k0<nv:v0+=p.response[w,c,0,k0]*(value-old)
                    if k1<nv:v1+=p.response[w,c,0,k1]*(value-old)
                    if lane==0:p.contact_impulse[w,c,0]=value
                    v0=warp_barrier(v0)
                if unchanged:break
            if k0<nv:p.velocity[w,k0]=v0
            if k1<nv:p.velocity[w,k1]=v1
            v0=warp_barrier(v0)
            wp.tile_assign(v,wp.tile_load(p.velocity,shape=(1,nv),offset=(w,0)))
'''

CHECK='''                if it%8==7:
                    change=warp_max(wp.max(wp.abs(v0-before0),wp.abs(v1-before1)))
                    magnitude=warp_max(wp.max(wp.abs(v0),wp.abs(v1)))
                    if change<=2e-6+9.5367431640625e-7*magnitude:
                        # Absolute plus float32 roundoff bound in the row's
                        # velocity units. This tests original equations, not
                        # just a small net change from cancelling corrections.
                        valid=bool(True)
                        for c in range(p.nlimit[w]):
                            dot=float(0.);scale=float(0.)
                            if k0<nv:
                                term=p.limit_J[w,c,k0]*v0;dot+=term;scale+=wp.abs(term)
                            if k1<nv:
                                term=p.limit_J[w,c,k1]*v1;dot+=term;scale+=wp.abs(term)
                            speed=warp_sum(dot);norm=warp_sum(scale)
                            gap=speed+p.limit_compliance[w,c]*p.limit_impulse[w,c]-p.limit_target[w,c]
                            residual=wp.max(0.,-gap)
                            if p.limit_bilateral[w,c]!=0 or p.limit_impulse[w,c]>0.:residual=wp.abs(gap)
                            if residual>2e-6+9.5367431640625e-7*norm:valid=False
                        for c in range(p.ncontact[w]):
                            dot=float(0.);scale=float(0.)
                            if k0<nv:
                                term=p.J[w,c,0,k0]*v0;dot+=term;scale+=wp.abs(term)
                            if k1<nv:
                                term=p.J[w,c,0,k1]*v1;dot+=term;scale+=wp.abs(term)
                            speed=warp_sum(dot);norm=warp_sum(scale)
                            residual=wp.max(0.,-speed)
                            if p.contact_impulse[w,c,0]>0.:residual=wp.abs(speed)
                            if residual>2e-6+9.5367431640625e-7*norm:valid=False
                            if p.friction[w,c]>0.:
                                dot1=float(0.);dot2=float(0.);scale=float(0.)
                                if k0<nv:
                                    t1=p.J[w,c,1,k0]*v0;t2=p.J[w,c,2,k0]*v0
                                    dot1+=t1;dot2+=t2;scale+=wp.abs(t1)+wp.abs(t2)
                                if k1<nv:
                                    t1=p.J[w,c,1,k1]*v1;t2=p.J[w,c,2,k1]*v1
                                    dot1+=t1;dot2+=t2;scale+=wp.abs(t1)+wp.abs(t2)
                                speed1=warp_sum(dot1);speed2=warp_sum(dot2);norm=warp_sum(scale)
                                old1=p.contact_impulse[w,c,1];old2=p.contact_impulse[w,c,2]
                                t1=old1-speed1/p.diagonal[w,c,1];t2=old2-speed2/p.diagonal[w,c,2]
                                bounds=friction_bound(p,w,c);length=wp.sqrt(t1*t1+t2*t2)
                                ratio=wp.min(1.,bounds[0]/wp.max(length,1e-30))
                                residual=wp.max(wp.abs(t1*ratio-old1)*p.diagonal[w,c,1],wp.abs(t2*ratio-old2)*p.diagonal[w,c,2])
                                if residual>2e-6+9.5367431640625e-7*norm:valid=False
                                if p.manifold.enabled:
                                    g=p.manifold.group[w,c]
                                    if p.manifold.size[w,g]>1:
                                        dot=float(0.);scale=float(0.)
                                        if k0<nv:
                                            term=p.manifold.J[w,g,2,k0]*v0;dot+=term;scale+=wp.abs(term)
                                        if k1<nv:
                                            term=p.manifold.J[w,g,2,k1]*v1;dot+=term;scale+=wp.abs(term)
                                        speed=warp_sum(dot);norm=warp_sum(scale)
                                        old=p.manifold.impulse[w,g,2]
                                        expected=wp.clamp(old-speed/p.manifold.diagonal[w,g,2],-bounds[1],bounds[1])
                                        residual=wp.abs(expected-old)*p.manifold.diagonal[w,g,2]
                                        if residual>2e-6+9.5367431640625e-7*norm:valid=False
                        if valid:break
'''

METRIC='''            for c in range(p.ncontact[w]):
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
                        metric[w,c,0]=d1*common;metric[w,c,1]=d2*common
            if p.manifold.enabled:
                for g in range(p.manifold.count[w]):
                    metric_js=wp.tile_load(p.manifold.J[w,g,2],shape=(nv,))
                    metric_rs=wp.tile_load(p.manifold.response[w,g,2],shape=(nv,))
                    ds=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,metric_js,metric_rs)),0)
                    if lane==0:metric[w,g,2]=wp.max(ds,1e-12)
'''

def generate(accelerated=False,precondition=False):
 # Frozen pre-change equations: do not generate a candidate from itself after
 # the approved implementation becomes the default production solver.
 source=(ROOT/'Saved/MimicKitEquipment/floor-recovery/block_contact_before_reset_speed.py').read_text()
 source=source.replace('\ndef make_block_iteration',NATIVE+'\ndef make_block_iteration',1)
 source=source.replace('    @wp.kernel(module=', '    assert 0<nv<=64, "Register sweep requires <=64 DOFs and block_dim=32"\n    @wp.kernel(module=',1)
 begin=source.index('            for it in range(iterations):')
 end=source.index('            changed=bool(False)',begin)
 loop=LOOP
 if precondition:
  source=source.replace('iterations:int,error:wp.array(dtype=int)):', 'iterations:int,error:wp.array(dtype=int),metric:wp.array3d(dtype=float)):')
  loop=METRIC+loop.replace('p.diagonal[w,c,1]','metric[w,c,0]').replace('p.diagonal[w,c,2]','metric[w,c,1]').replace('p.manifold.diagonal[w,g,2]','metric[w,g,2]')
 if accelerated:
  loop=loop.replace('p.relaxation','1.0')
  loop=loop.replace('                unchanged=bool(True)','                before0=v0;before1=v1\n                unchanged=bool(True)')
  # Separate names prevent Warp from aliasing sweep/check temporaries.
  import re
  check=CHECK
  for name in ('c','g','dot','dot1','dot2','scale','speed','speed1','speed2','old','old1','old2','t1','t2','bounds','length'):
   check=re.sub(r'\b'+name+r'\b','check_'+name,check)
  loop=loop.replace('                if unchanged:break', '                if unchanged:break\n'+check)
 begin=source.index('            for it in range(iterations):')
 end=source.index('            changed=bool(False)',begin)
 source=source[:begin]+loop+source[end:]
 path=ROOT/'Saved/MimicKitEquipment/floor-recovery'/('block_contact_preconditioned_candidate.py' if precondition else 'block_contact_accelerated_candidate.py' if accelerated else 'block_contact_register_candidate.py')
 path.write_text(source)
 return path

if __name__=='__main__':print(generate())
