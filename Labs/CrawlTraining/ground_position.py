"""Experimental split ground-position recovery; not installed in training.

Analytic sphere/capsule/box support against the existing horizontal plane.
Uses generalized inverse mass and changes positions only. Jolt defaults:
2cm penetration slop, 20cm correction cap, 0.2 Baumgarte relaxation.
"""
import numpy as np
import warp as wp
import mujoco
from mujoco_warp._src import smooth, support
from limit_projection_gpu import integrate


@wp.kernel(enable_backward=False)
def rows(geoms:wp.array(dtype=int),local:wp.array(dtype=wp.vec3),radius:wp.array(dtype=float),
         xpos:wp.array2d(dtype=wp.vec3),xmat:wp.array2d(dtype=wp.mat33),
         bodies:wp.array(dtype=int),parents:wp.array(dtype=int),roots:wp.array(dtype=int),
         dofbodies:wp.array(dtype=int),com:wp.array2d(dtype=wp.vec3),cdof:wp.array2d(dtype=wp.spatial_vector),
         floor:float,slop:float,J:wp.array3d(dtype=float),depth:wp.array2d(dtype=float)):
    w,c,j=wp.tid();g=geoms[c]
    point=xpos[w,g]+xmat[w,g]*local[c]-wp.vec3(0.,0.,radius[c])
    separation=point[2]-floor+slop
    if j==0:depth[w,c]=separation
    value=float(0.)
    if separation<0.:
        linear,angular=support.jac_dof(parents,roots,dofbodies,com,cdof,point,bodies[g],j,w)
        value=linear[2]
    J[w,c,j]=value


@wp.kernel(enable_backward=False)
def response(J:wp.array3d(dtype=float),inverse:wp.array3d(dtype=float),out:wp.array3d(dtype=float)):
    w,c,j=wp.tid();v=float(0.)
    for k in range(J.shape[2]):v+=inverse[w,j,k]*J[w,c,k]
    out[w,c,j]=v


@wp.kernel(enable_backward=False)
def solve(J:wp.array3d(dtype=float),response:wp.array3d(dtype=float),depth:wp.array2d(dtype=float),
          diagonal:wp.array2d(dtype=float),delta:wp.array2d(dtype=float),impulse:wp.array2d(dtype=float)):
    w=wp.tid();nv=J.shape[2];nc=J.shape[1]
    for j in range(nv):delta[w,j]=0.
    for c in range(nc):
        impulse[w,c]=0.;den=float(0.)
        for j in range(nv):den+=J[w,c,j]*response[w,c,j]
        diagonal[w,c]=den
    for iteration in range(20):
        for c in range(nc):
            if depth[w,c]>=0. or diagonal[w,c]<1e-12:continue
            residual=wp.max(depth[w,c],-.2)*.2
            for j in range(nv):residual+=J[w,c,j]*delta[w,j]
            old=impulse[w,c];value=wp.max(0.,old-residual/diagonal[w,c]);change=value-old
            impulse[w,c]=value
            for j in range(nv):delta[w,j]+=response[w,c,j]*change


@wp.kernel(enable_backward=False)
def apply_delta(qpos:wp.array2d(dtype=float),delta:wp.array2d(dtype=float),qadr:wp.array(dtype=int),
                dadr:wp.array(dtype=int),kind:wp.array(dtype=int)):
    w,j=wp.tid();qa=qadr[j];da=dadr[j]
    if kind[j]==0:
        for k in range(3):qpos[w,qa+k]+=delta[w,da+k]
        integrate(qpos,w,qa+3,wp.vec3(delta[w,da+3],delta[w,da+4],delta[w,da+5]))
    elif kind[j]==1:integrate(qpos,w,qa,wp.vec3(delta[w,da],delta[w,da+1],delta[w,da+2]))
    else:qpos[w,qa]+=delta[w,da]


class GroundPosition:
    def __init__(self,m,wm,d,device):
        floors=[g for g in range(m.ngeom) if m.geom_type[g]==mujoco.mjtGeom.mjGEOM_PLANE]
        assert len(floors)==1
        floor=floors[0];assert m.geom_bodyid[floor]==0
        np.testing.assert_allclose(m.geom_quat[floor],[1,0,0,0],atol=1e-7)
        self.floor=float(m.geom_pos[floor,2]);self.slop=.02
        geoms=[];points=[];radii=[]
        for g in range(m.ngeom):
            if not m.geom_bodyid[g]:continue
            if not ((m.geom_contype[g]&m.geom_conaffinity[floor]) or (m.geom_contype[floor]&m.geom_conaffinity[g])):continue
            size=m.geom_size[g];kind=m.geom_type[g]
            if kind==mujoco.mjtGeom.mjGEOM_BOX:
                pp=[np.array([x,y,z])*size for x in (-1,1) for y in (-1,1) for z in (-1,1)];r=0.
            elif kind==mujoco.mjtGeom.mjGEOM_CAPSULE:pp=[[0,0,-size[1]],[0,0,size[1]]];r=size[0]
            elif kind==mujoco.mjtGeom.mjGEOM_SPHERE:pp=[[0,0,0]];r=size[0]
            else:raise ValueError('Unsupported ground primitive')
            geoms.extend([g]*len(pp));points.extend(pp);radii.extend([r]*len(pp))
        self.geoms=wp.array(geoms,dtype=int,device=device);self.points=wp.array(points,dtype=wp.vec3,device=device)
        self.radius=wp.array(radii,dtype=float,device=device);self.nc=len(geoms);self.nv=m.nv
        self.J=wp.zeros((d.nworld,self.nc,m.nv),device=device);self.response=wp.empty_like(self.J)
        self.depth=wp.zeros((d.nworld,self.nc),device=device);self.diagonal=wp.empty_like(self.depth)
        self.impulse=wp.empty_like(self.depth);self.delta=wp.zeros((d.nworld,m.nv),device=device)
        self.qadr=wp.array(m.jnt_qposadr,dtype=int,device=device);self.dadr=wp.array(m.jnt_dofadr,dtype=int,device=device)
        self.kind=wp.array(m.jnt_type,dtype=int,device=device);self.nj=m.njnt
        self.m=wm;self.d=d;self.device=device

    def apply(self,inverse,passes=4):
        m=self.m;d=self.d
        for _ in range(passes):
            smooth.kinematics(m,d);smooth.com_pos(m,d)
            wp.launch(rows,dim=(d.nworld,self.nc,self.nv),inputs=[self.geoms,self.points,self.radius,d.geom_xpos,d.geom_xmat,
                m.geom_bodyid,m.body_parentid,m.body_rootid,m.dof_bodyid,d.subtree_com,d.cdof,self.floor,self.slop,self.J,self.depth],device=self.device)
            wp.launch(response,dim=(d.nworld,self.nc,self.nv),inputs=[self.J,inverse,self.response],device=self.device)
            wp.launch(solve,dim=d.nworld,inputs=[self.J,self.response,self.depth,self.diagonal,self.delta,self.impulse],device=self.device)
            wp.launch(apply_delta,dim=(d.nworld,self.nj),inputs=[d.qpos,self.delta,self.qadr,self.dadr,self.kind],device=self.device)
