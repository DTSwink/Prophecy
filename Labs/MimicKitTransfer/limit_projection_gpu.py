"""Split-position angular constraints for the Jolt-matching training profile.

Uses a frozen per-substep generalized mass metric and re-evaluates angular error
after each correction. Root/parents move according to mass; velocities are not
changed. The scalar path remains an independent GPU implementation for diagnostics.
"""
import numpy as np
import warp as wp
from mujoco_warp._src import math as mm


@wp.func
def bound_parameters(limit:wp.vec3):
    return wp.vec4(wp.sin(.5*limit[0]),wp.sin(.5*limit[1]),wp.sin(.5*limit[2]),wp.cos(.5*limit[0]))


@wp.func
def project_rotation(q:wp.quat,bounds:wp.vec4):
    norm=wp.sqrt(q[0]*q[0]+q[3]*q[3])
    twist=wp.quat_identity()
    if norm>1e-12:twist=wp.quat(q[0]/norm,0.,0.,q[3]/norm)
    swing=q*wp.quat_inverse(twist)
    if swing[3]<0.:swing=-swing
    if twist[3]<0.:twist=-twist
    changed=bool(False)
    if wp.abs(twist[0])>bounds[0]:
        twist=wp.quat(wp.sign(twist[0])*bounds[0],0.,0.,bounds[3]);changed=True
    ay=bounds[1];az=bounds[2];y=swing[1];z=swing[2]
    if y*y/(ay*ay)+z*z/(az*az)>1.:
        changed=True;lo=float(0.);hi=wp.sqrt(ay*ay*y*y+az*az*z*z)
        for _ in range(30):
            mid=(lo+hi)*.5
            ny=ay*y/(ay*ay+mid);nz=az*z/(az*az+mid)
            if ny*ny+nz*nz>1.:lo=mid
            else:hi=mid
        root=(lo+hi)*.5;cy=ay*ay*y/(ay*ay+root);cz=az*az*z/(az*az+root)
        swing=wp.quat(0.,cy,cz,wp.sqrt(wp.max(0.,1.-cy*cy-cz*cz)))
    return swing*twist,changed


@wp.func
def clamp_rotation(q:wp.quat,limit:wp.vec3):
    result,changed=project_rotation(q,bound_parameters(limit))
    return result


@wp.func
def angular_error_bounds(q:wp.quat,bounds:wp.vec4):
    result,changed=project_rotation(q,bounds)
    # Interior rotations need exactly zero correction, not the float32
    # residual of decomposing/recomposing an unchanged quaternion.
    if not changed:return wp.vec3(0.)
    delta=wp.quat_inverse(result)*q
    if delta[3]<0.:delta=-delta
    return 2.*wp.vec3(delta[0],delta[1],delta[2])


@wp.func
def angular_error(q:wp.quat,limit:wp.vec3):
    return angular_error_bounds(q,bound_parameters(limit))


@wp.func
def integrate(q:wp.array2d(dtype=float),w:int,qa:int,v:wp.vec3):
    cur=wp.quat(q[w,qa],q[w,qa+1],q[w,qa+2],q[w,qa+3])
    value=mm.quat_integrate(cur,v,1.)
    for k in range(4):q[w,qa+k]=value[k]


@wp.kernel(enable_backward=False)
def project(q:wp.array2d(dtype=float),inverse:wp.array3d(dtype=float),
            qadr:wp.array(dtype=int),dadr:wp.array(dtype=int),kind:wp.array(dtype=int),
            reference:wp.array(dtype=wp.quat),limits:wp.array(dtype=wp.vec3),
            ranges:wp.array(dtype=wp.vec2),delta:wp.array2d(dtype=float),iterations:int):
    w=wp.tid();nj=qadr.shape[0];nv=inverse.shape[1]
    for _ in range(iterations):
        for j in range(1,nj):
            qa=qadr[j];da=dadr[j];err=wp.vec3(0.);scalar=float(0.)
            if kind[j]==1:
                rotation=wp.quat(q[w,qa+1],q[w,qa+2],q[w,qa+3],q[w,qa])
                err=angular_error(reference[j]*rotation,limits[j])
            else:scalar=q[w,qa]-wp.clamp(q[w,qa],ranges[j][0],ranges[j][1])
            if wp.length_sq(err)>1e-16 or wp.abs(scalar)>1e-8:
                impulse=wp.vec3(0.)
                if kind[j]==1:
                    matrix=wp.mat33(0.)
                    for a in range(3):
                        for b in range(3):matrix[a,b]=inverse[w,da+a,da+b]
                    impulse=wp.inverse(matrix)*(-.2*err)
                else:impulse=wp.vec3(-.2*scalar/inverse[w,da,da],0.,0.)
                for k in range(nv):
                    value=inverse[w,k,da]*impulse[0]
                    if kind[j]==1:value+=inverse[w,k,da+1]*impulse[1]+inverse[w,k,da+2]*impulse[2]
                    delta[w,k]=value
                for b in range(nj):
                    bq=qadr[b];bd=dadr[b]
                    if kind[b]==0:
                        for k in range(3):q[w,bq+k]+=delta[w,bd+k]
                        integrate(q,w,bq+3,wp.vec3(delta[w,bd+3],delta[w,bd+4],delta[w,bd+5]))
                    elif kind[b]==1:integrate(q,w,bq,wp.vec3(delta[w,bd],delta[w,bd+1],delta[w,bd+2]))
                    else:q[w,bq]+=delta[w,bd]


@wp.kernel(enable_backward=False)
def prepare_bounds(limits:wp.array(dtype=wp.vec3),bounds:wp.array(dtype=wp.vec4)):
    j=wp.tid();bounds[j]=bound_parameters(limits[j])


class SplitLimitProjection:
    def __init__(self,m,d,metadata,device):
        refs=np.tile([0.,0.,0.,1.],(m.njnt,1));angles=np.ones((m.njnt,3))
        for idx,row in metadata:
            if row['kind']=='ball':
                assert row['modes']==[1,1,1]
                refs[idx]=np.roll(row['reference_wxyz'],-1);angles[idx]=row['limits_rad']
        self.qadr=wp.array(m.jnt_qposadr,dtype=int,device=device)
        self.dadr=wp.array(m.jnt_dofadr,dtype=int,device=device)
        self.kind=wp.array(m.jnt_type,dtype=int,device=device)
        self.reference=wp.array(refs,dtype=wp.quat,device=device)
        self.limits=wp.array(angles,dtype=wp.vec3,device=device)
        self.ranges=wp.array(m.jnt_range,dtype=wp.vec2,device=device)
        self.bounds=wp.empty(m.njnt,dtype=wp.vec4,device=device)
        wp.launch(prepare_bounds,dim=m.njnt,inputs=[self.limits,self.bounds],device=device)
        self.delta=wp.zeros((d.nworld,m.nv),dtype=float,device=device)
        self.sync=wp.zeros(d.nworld,dtype=float,device=device)
        self.tiled_kernel=make_tiled_projection(m.nv,m.njnt)
        self.shared_kernel=make_shared_projection(m.nv,m.njnt)
        self.data=d;self.device=device

    def apply(self,inverse,iterations=20,tiled=False,shared=False):
        args=[self.data.qpos,inverse,self.qadr,self.dadr,self.kind,self.reference,self.limits,self.ranges,self.delta,iterations]
        if shared:
            args[6]=self.bounds
            wp.launch(self.shared_kernel,dim=(self.data.nworld,32),inputs=args,block_dim=32,device=self.device)
        elif tiled:
            assert self.qadr.shape[0]<=32
            wp.launch(self.tiled_kernel,dim=(self.data.nworld,32),inputs=args+[self.sync],block_dim=32,device=self.device)
        else:wp.launch(project,dim=self.data.nworld,inputs=args,device=self.device)


@wp.func
def update_joint_tiled(b:int,q:wp.array2d(dtype=float),delta:wp.array2d(dtype=float),
                       qadr:wp.array(dtype=int),dadr:wp.array(dtype=int),kind:wp.array(dtype=int),w:int):
    if b>=qadr.shape[0]:return float(0.)
    qa=qadr[b];da=dadr[b]
    if kind[b]==0:
        for k in range(3):q[w,qa+k]+=delta[w,da+k]
        integrate(q,w,qa+3,wp.vec3(delta[w,da+3],delta[w,da+4],delta[w,da+5]))
    elif kind[b]==1:integrate(q,w,qa,wp.vec3(delta[w,da],delta[w,da+1],delta[w,da+2]))
    else:q[w,qa]+=delta[w,da]
    return q[w,qa]


def make_tiled_projection(nv,nj):
    @wp.kernel(module='unique',enable_backward=False)
    def tiled(q:wp.array2d(dtype=float),inverse:wp.array3d(dtype=float),
              qadr:wp.array(dtype=int),dadr:wp.array(dtype=int),kind:wp.array(dtype=int),
              reference:wp.array(dtype=wp.quat),limits:wp.array(dtype=wp.vec3),
              ranges:wp.array(dtype=wp.vec2),delta:wp.array2d(dtype=float),iterations:int,sync:wp.array(dtype=float)):
        w,bone=wp.tid()
        inv=wp.tile_load(inverse[w],shape=(nv,nv),storage='shared')
        for _ in range(iterations):
            for j in range(1,nj):
                qa=qadr[j];da=dadr[j];err=wp.vec3(0.);scalar=float(0.)
                if kind[j]==1:
                    rotation=wp.quat(q[w,qa+1],q[w,qa+2],q[w,qa+3],q[w,qa])
                    err=angular_error(reference[j]*rotation,limits[j])
                else:scalar=q[w,qa]-wp.clamp(q[w,qa],ranges[j][0],ranges[j][1])
                if wp.length_sq(err)>1e-16 or wp.abs(scalar)>1e-8:
                    impulse=wp.vec3(0.)
                    if kind[j]==1:
                        matrix=wp.mat33(0.)
                        for a in range(3):
                            for b in range(3):matrix[a,b]=inverse[w,da+a,da+b]
                        impulse=wp.inverse(matrix)*(-.2*err)
                    else:impulse=wp.vec3(-.2*scalar/inverse[w,da,da],0.,0.)
                    r0=wp.tile_view(inv,offset=(da,0),shape=(1,nv))
                    change=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')
                    wp.tile_assign(change,r0*impulse[0])
                    if kind[j]==1:
                        r1=wp.tile_view(inv,offset=(da+1,0),shape=(1,nv))
                        r2=wp.tile_view(inv,offset=(da+2,0),shape=(1,nv))
                        wp.tile_assign(change,change+r1*impulse[1]+r2*impulse[2])
                    wp.tile_store(delta,change,offset=(w,0))
                    updated=wp.tile(update_joint_tiled(bone,q,delta,qadr,dadr,kind,w))
                    result=wp.tile_sum(updated)
                    wp.tile_store(sync,result,offset=(w,))
    return tiled


def make_shared_projection(nv,nj):
    # One lane integrates one complete joint quaternion. The previous kernel
    # assigned one lane per component, recomputing each quaternion four times.
    assert nj+1<=32
    @wp.kernel(module='unique',enable_backward=False)
    def shared(q:wp.array2d(dtype=float),inverse:wp.array3d(dtype=float),
               qadr:wp.array(dtype=int),dadr:wp.array(dtype=int),kind:wp.array(dtype=int),
               reference:wp.array(dtype=wp.quat),limits:wp.array(dtype=wp.vec4),
               ranges:wp.array(dtype=wp.vec2),delta:wp.array2d(dtype=float),iterations:int):
        w,lane=wp.tid()
        inv=wp.tile_load(inverse[w],shape=(nv,nv),storage='shared')
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
