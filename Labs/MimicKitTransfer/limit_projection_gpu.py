"""Isolated split-position angular constraint prototype.

Uses a frozen per-substep generalized mass metric and re-evaluates angular error
after each correction. Root/parents move according to mass; velocities are not
changed. Neither this projection nor the contact experiment is a training default.
"""
import numpy as np
import warp as wp
from mujoco_warp._src import math as mm


@wp.func
def clamp_rotation(q:wp.quat,limit:wp.vec3):
    # Warp quaternion operations here use XYZW; convert at the array boundary.
    norm=wp.sqrt(q[0]*q[0]+q[3]*q[3])
    twist=wp.quat_identity()
    if norm>1e-12:twist=wp.quat(q[0]/norm,0.,0.,q[3]/norm)
    swing=q*wp.quat_inverse(twist)
    if swing[3]<0.:swing=-swing
    if twist[3]<0.:twist=-twist
    bound=wp.sin(.5*limit[0])
    if wp.abs(twist[0])>bound:twist=wp.quat(wp.sign(twist[0])*bound,0.,0.,wp.cos(.5*limit[0]))
    ay=wp.sin(.5*limit[1]);az=wp.sin(.5*limit[2]);y=swing[1];z=swing[2]
    if y*y/(ay*ay)+z*z/(az*az)>1.:
        lo=float(0.);hi=wp.sqrt(ay*ay*y*y+az*az*z*z)
        for _ in range(30):
            mid=(lo+hi)*.5
            ny=ay*y/(ay*ay+mid);nz=az*z/(az*az+mid)
            if ny*ny+nz*nz>1.:lo=mid
            else:hi=mid
        root=(lo+hi)*.5;cy=ay*ay*y/(ay*ay+root);cz=az*az*z/(az*az+root)
        swing=wp.quat(0.,cy,cz,wp.sqrt(wp.max(0.,1.-cy*cy-cz*cz)))
    return swing*twist


@wp.func
def angular_error(q:wp.quat,limit:wp.vec3):
    delta=wp.quat_inverse(clamp_rotation(q,limit))*q
    if delta[3]<0.:delta=-delta
    return 2.*wp.vec3(delta[0],delta[1],delta[2])


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
        self.delta=wp.zeros((d.nworld,m.nv),dtype=float,device=device)
        self.sync=wp.zeros(d.nworld,dtype=float,device=device)
        self.tiled_kernel=make_tiled_projection(m.nv,m.njnt)
        size=1<<(m.nq-1).bit_length()
        mapping=np.zeros((size,4),np.int32)
        for j in range(m.njnt):
            qa=m.jnt_qposadr[j];da=m.jnt_dofadr[j];kind=int(m.jnt_type[j])
            if kind==0:
                for k in range(3):mapping[qa+k]=[qa+k,da+k,0,0]
                for k in range(4):mapping[qa+3+k]=[qa+3,da+3,1,k]
            elif kind==1:
                for k in range(4):mapping[qa+k]=[qa,da,1,k]
            else:mapping[qa]=[qa,da,0,0]
        self.qmap=wp.array(mapping,dtype=wp.vec4i,device=device)
        self.shared_kernel=make_shared_projection(m.nv,m.njnt,size)
        self.shared_size=size
        self.data=d;self.device=device

    def apply(self,inverse,iterations=20,tiled=False,shared=False):
        args=[self.data.qpos,inverse,self.qadr,self.dadr,self.kind,self.reference,self.limits,self.ranges,self.delta,iterations]
        if shared:
            wp.launch(self.shared_kernel,dim=(self.data.nworld,self.shared_size),inputs=args+[self.qmap],block_dim=self.shared_size,device=self.device)
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


def make_shared_projection(nv,nj,size):
    @wp.kernel(module='unique',enable_backward=False)
    def shared(q:wp.array2d(dtype=float),inverse:wp.array3d(dtype=float),
               qadr:wp.array(dtype=int),dadr:wp.array(dtype=int),kind:wp.array(dtype=int),
               reference:wp.array(dtype=wp.quat),limits:wp.array(dtype=wp.vec3),
               ranges:wp.array(dtype=wp.vec2),delta:wp.array2d(dtype=float),iterations:int,
               mapping:wp.array(dtype=wp.vec4i)):
        w,lane=wp.tid()
        inv=wp.tile_load(inverse[w],shape=(nv,nv),storage='shared')
        pose=wp.tile_load(q,shape=(1,size),offset=(w,0),storage='shared')
        mp=mapping[lane]
        for _ in range(iterations):
            active=bool(False)
            for j in range(1,nj):
                qa=qadr[j];da=dadr[j];err=wp.vec3(0.);scalar=float(0.)
                if kind[j]==1:
                    rotation=wp.quat(wp.tile_extract(pose,0,qa+1),wp.tile_extract(pose,0,qa+2),wp.tile_extract(pose,0,qa+3),wp.tile_extract(pose,0,qa))
                    err=angular_error(reference[j]*rotation,limits[j])
                else:
                    value=wp.tile_extract(pose,0,qa)
                    scalar=value-wp.clamp(value,ranges[j][0],ranges[j][1])
                if wp.length_sq(err)>1e-16 or wp.abs(scalar)>1e-8:
                    active=True;impulse=wp.vec3(0.)
                    if kind[j]==1:
                        matrix=wp.mat33(0.)
                        for a in range(3):
                            for b in range(3):matrix[a,b]=wp.tile_extract(inv,da+a,da+b)
                        impulse=wp.inverse(matrix)*(-.2*err)
                    else:impulse=wp.vec3(-.2*scalar/wp.tile_extract(inv,da,da),0.,0.)
                    r0=wp.tile_view(inv,offset=(da,0),shape=(1,nv))
                    change=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')
                    wp.tile_assign(change,r0*impulse[0])
                    if kind[j]==1:
                        r1=wp.tile_view(inv,offset=(da+1,0),shape=(1,nv))
                        r2=wp.tile_view(inv,offset=(da+2,0),shape=(1,nv))
                        wp.tile_assign(change,change+r1*impulse[1]+r2*impulse[2])
                    updated=float(0.)
                    if lane<q.shape[1]:
                        if mp[2]==1:
                            cur=wp.quat(wp.tile_extract(pose,0,mp[0]),wp.tile_extract(pose,0,mp[0]+1),wp.tile_extract(pose,0,mp[0]+2),wp.tile_extract(pose,0,mp[0]+3))
                            direction=wp.vec3(wp.tile_extract(change,0,mp[1]),wp.tile_extract(change,0,mp[1]+1),wp.tile_extract(change,0,mp[1]+2))
                            rotated=mm.quat_integrate(cur,direction,1.)
                            updated=rotated[mp[3]]
                        else:updated=wp.tile_extract(pose,0,mp[0])+wp.tile_extract(change,0,mp[1])
                    # Construct the new tile before overwriting pose: every lane
                    # must read the previous quaternion, never a partial update.
                    values=wp.tile(updated)
                    wp.tile_assign(pose,wp.tile_reshape(values,shape=(1,size)))
            if not active:break
        wp.tile_store(q,pose,offset=(w,0))
    return shared
