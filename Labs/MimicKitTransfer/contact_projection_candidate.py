"""LOCAL DIAGNOSTIC ONLY: contact-constrained split projection candidate.
REJECTED: matched bad case still penetrates5.58cm. Not packaged or selected by training.
"""
import warp as wp
from mujoco_warp._src import math as mm
from sequential_contact_gpu import ContactProblem
from limit_projection_gpu import angular_error_bounds

def make_contact_projection(nv,nj):
    # One lane integrates one complete joint quaternion. The previous kernel
    # assigned one lane per component, recomputing each quaternion four times.
    assert nj+1<=32
    @wp.kernel(module='unique',enable_backward=False)
    def shared(q:wp.array2d(dtype=float),inverse:wp.array3d(dtype=float),
               qadr:wp.array(dtype=int),dadr:wp.array(dtype=int),kind:wp.array(dtype=int),
               reference:wp.array(dtype=wp.quat),limits:wp.array(dtype=wp.vec4),
               ranges:wp.array(dtype=wp.vec2),delta:wp.array2d(dtype=float),iterations:int,
               contact:ContactProblem,ids:wp.array2d(dtype=int),geom:wp.array(dtype=wp.vec2i),floor:int):
        w,lane=wp.tid()
        inv=wp.tile_load(inverse[w],shape=(nv,nv),storage='shared')
        # Diagnostic candidate: remove motion normal to already active floor
        # contacts from the split-correction mass metric, once per substep.
        # This does not alter the velocity solver or process self contacts.
        for c in range(contact.ncontact[w]):
            pair=geom[ids[w,c]]
            if pair[0]==floor or pair[1]==floor:
                jac=wp.tile_load(contact.J[w,c],shape=(1,nv))
                response=wp.tile_matmul(jac,inv)
                den=wp.tile_extract(wp.tile_matmul(response,wp.tile_transpose(jac)),0,0)
                if den>1e-5*contact.diagonal[w,c,0]:
                    correction=wp.tile_matmul(wp.tile_transpose(response),response)*(1./den)
                    wp.tile_assign(inv,inv-correction)

        local=wp.vec4(0.);joint=lane-1;qa=int(0);da=int(0);ball=bool(False)
        if lane==0:local=wp.vec4(q[w,0],q[w,1],q[w,2],0.)
        elif joint<nj:
            qa=qadr[joint];da=dadr[joint]
            ball=kind[joint]==0 or kind[joint]==1
            if joint==0:qa+=3;da+=3
            local[0]=q[w,qa]
            if ball:local=wp.vec4(q[w,qa],q[w,qa+1],q[w,qa+2],q[w,qa+3])
        pose=wp.tile_zeros(shape=(4,32),dtype=float,storage='shared')
        wp.tile_assign(pose,wp.tile(local))
        local_inverse=wp.mat33(0.)
        if joint>0 and joint<nj and ball:
            matrix=wp.mat33(0.)
            for a in range(3):
                for b in range(3):matrix[a,b]=wp.tile_extract(inv,da+a,da+b)
            local_inverse=wp.inverse(matrix)
        inverse_blocks=wp.tile_zeros(shape=(3,3,32),dtype=float,storage='shared')
        wp.tile_assign(inverse_blocks,wp.tile(local_inverse))
        for _ in range(iterations):
            active=bool(False)
            for j in range(1,nj):
                jd=dadr[j];raw=wp.vec4(wp.tile_extract(pose,0,j+1),wp.tile_extract(pose,1,j+1),wp.tile_extract(pose,2,j+1),wp.tile_extract(pose,3,j+1));err=wp.vec3(0.);scalar=float(0.)
                if kind[j]==1:
                    err=angular_error_bounds(reference[j]*wp.quat(raw[1],raw[2],raw[3],raw[0]),limits[j])
                else:scalar=raw[0]-wp.clamp(raw[0],ranges[j][0],ranges[j][1])
                if wp.length_sq(err)>1e-16 or wp.abs(scalar)>1e-8:
                    active=True;impulse=wp.vec3(0.)
                    if kind[j]==1:
                        matrix=wp.mat33(0.)
                        for a in range(3):
                            for b in range(3):matrix[a,b]=wp.tile_extract(inverse_blocks,a,b,j+1)
                        impulse=matrix*(-.2*err)
                    else:impulse=wp.vec3(-.2*scalar/wp.tile_extract(inv,jd,jd),0.,0.)
                    r0=wp.tile_view(inv,offset=(jd,0),shape=(1,nv))
                    change=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')
                    wp.tile_assign(change,r0*impulse[0])
                    if kind[j]==1:
                        r1=wp.tile_view(inv,offset=(jd+1,0),shape=(1,nv))
                        r2=wp.tile_view(inv,offset=(jd+2,0),shape=(1,nv))
                        wp.tile_assign(change,change+r1*impulse[1]+r2*impulse[2])
                    updated=wp.vec4(wp.tile_extract(pose,0,lane),wp.tile_extract(pose,1,lane),wp.tile_extract(pose,2,lane),wp.tile_extract(pose,3,lane))
                    if lane==0:
                        for k in range(3):updated[k]+=wp.tile_extract(change,0,k)
                    elif joint<nj:
                        if ball:
                            cur=wp.quat(updated[0],updated[1],updated[2],updated[3])
                            direction=wp.vec3(wp.tile_extract(change,0,da),wp.tile_extract(change,0,da+1),wp.tile_extract(change,0,da+2))
                            rotated=mm.quat_integrate(cur,direction,1.)
                            updated=wp.vec4(rotated[0],rotated[1],rotated[2],rotated[3])
                        else:updated[0]+=wp.tile_extract(change,0,da)
                    wp.tile_assign(pose,wp.tile(updated))
            if not active:break
        final=wp.vec4(wp.tile_extract(pose,0,lane),wp.tile_extract(pose,1,lane),wp.tile_extract(pose,2,lane),wp.tile_extract(pose,3,lane))
        if lane==0:
            for k in range(3):q[w,k]=final[k]
        elif joint<nj:
            q[w,qa]=final[0]
            if ball:
                for k in range(1,4):q[w,qa+k]=final[k]
    # Keep the joint loop compact instead of duplicating the whole articulated
    # correction for each joint. This also greatly reduces first-use compilation.
    shared.module.options['max_unroll']=1
    return shared
