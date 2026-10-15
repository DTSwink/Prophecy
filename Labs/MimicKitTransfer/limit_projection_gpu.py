"""Isolated split-position angular constraint prototype.

Uses a frozen per-substep generalized mass metric and re-evaluates angular error
after each correction. Root/parents move according to mass; velocities are not
changed. Neither this projection nor the contact experiment is a training default.
"""
import numpy as np
import warp as wp
from mujoco_warp._src import math as mm


@wp.func
def angular_error(q:wp.quat,limit:wp.vec3):
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
    delta=wp.quat_inverse(swing*twist)*q
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
        self.data=d;self.device=device

    def apply(self,inverse,iterations=20):
        wp.launch(project,dim=self.data.nworld,inputs=[self.data.qpos,inverse,self.qadr,self.dadr,self.kind,
            self.reference,self.limits,self.ranges,self.delta,iterations],device=self.device)
