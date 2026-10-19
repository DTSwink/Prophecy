"""Floor-feasible angular-limit position correction, entirely GPU/capture safe.

Backtrack only the extra split-position correction when it would move a collider
through the static horizontal floor. Do not translate the whole character, edit
velocities, change angular limit values or inspect self collisions. Blocked split
corrections are deferred; this is not a simultaneous contact/limit position solve.
Existing penetration
from integration is not repaired here; the contact solver remains responsible.
"""
import numpy as np
import warp as wp
from mujoco_warp._src import math as mm


@wp.struct
class FloorGeometry:
    parent: wp.array(dtype=int)
    joint: wp.array(dtype=int)
    joint_count: wp.array(dtype=int)
    body_pos: wp.array(dtype=wp.vec3)
    body_quat: wp.array(dtype=wp.quat)
    kind: wp.array(dtype=int)
    qadr: wp.array(dtype=int)
    anchor: wp.array(dtype=wp.vec3)
    axis: wp.array(dtype=wp.vec3)
    rest: wp.array(dtype=float)
    geom_body: wp.array(dtype=int)
    geom_type: wp.array(dtype=int)
    geom_pos: wp.array(dtype=wp.vec3)
    geom_quat: wp.array(dtype=wp.quat)
    geom_size: wp.array(dtype=wp.vec3)
    position: wp.array2d(dtype=wp.vec3)
    rotation: wp.array2d(dtype=wp.quat)
    bound: wp.array2d(dtype=float)
    floor_z: float


@wp.func
def blended_quat(a:wp.array2d(dtype=float),b:wp.array2d(dtype=float),w:int,qa:int,t:float):
    x=wp.quat(a[w,qa],a[w,qa+1],a[w,qa+2],a[w,qa+3])
    y=wp.quat(b[w,qa],b[w,qa+1],b[w,qa+2],b[w,qa+3])
    if wp.dot(x,y)<0.:y=-y
    return wp.normalize((1.-t)*x+t*y)


@wp.func
def floor_fk(s:FloorGeometry,a:wp.array2d(dtype=float),b:wp.array2d(dtype=float),w:int,t:float):
    # Same joint-anchor FK equations as mujoco_warp.smooth._kinematics.
    s.position[w,0]=wp.vec3(0.);s.rotation[w,0]=wp.quat(1.,0.,0.,0.)
    for body in range(1,s.parent.shape[0]):
        j=s.joint[body];parent=s.parent[body]
        pos=s.position[w,parent]+mm.rot_vec_quat(s.body_pos[body],s.rotation[w,parent])
        rot=mm.mul_quat(s.rotation[w,parent],s.body_quat[body])
        for offset in range(s.joint_count[body]):
            idx=j+offset;qa=s.qadr[idx];kind=s.kind[idx]
            if kind==0:
                pos=wp.vec3((1.-t)*a[w,qa]+t*b[w,qa],(1.-t)*a[w,qa+1]+t*b[w,qa+1],(1.-t)*a[w,qa+2]+t*b[w,qa+2])
                rot=blended_quat(a,b,w,qa+3,t)
            else:
                anchor=pos+mm.rot_vec_quat(s.anchor[idx],rot)
                if kind==1:
                    rot=mm.mul_quat(rot,blended_quat(a,b,w,qa,t))
                    pos=anchor-mm.rot_vec_quat(s.anchor[idx],rot)
                elif kind==3:
                    angle=(1.-t)*a[w,qa]+t*b[w,qa]-s.rest[qa]
                    rot=mm.mul_quat(rot,mm.axis_angle_to_quat(s.axis[idx],angle))
                    pos=anchor-mm.rot_vec_quat(s.anchor[idx],rot)
                elif kind==2:
                    pos+=mm.rot_vec_quat(s.axis[idx],rot)*((1.-t)*a[w,qa]+t*b[w,qa]-s.rest[qa])
        s.position[w,body]=pos;s.rotation[w,body]=wp.normalize(rot)


@wp.func
def floor_height(s:FloorGeometry,w:int,g:int):
    body=s.geom_body[g]
    pos=s.position[w,body]+mm.rot_vec_quat(s.geom_pos[g],s.rotation[w,body])
    rot=mm.mul_quat(s.rotation[w,body],s.geom_quat[g]);size=s.geom_size[g]
    extent=size[0]
    if s.geom_type[g]==3:
        extent+=size[1]*wp.abs(mm.rot_vec_quat(wp.vec3(0.,0.,1.),rot)[2])
    elif s.geom_type[g]==6:
        extent=wp.abs(mm.rot_vec_quat(wp.vec3(size[0],0.,0.),rot)[2])+wp.abs(mm.rot_vec_quat(wp.vec3(0.,size[1],0.),rot)[2])+wp.abs(mm.rot_vec_quat(wp.vec3(0.,0.,size[2]),rot)[2])
    return pos[2]-extent-s.floor_z


@wp.func
def feasible(s:FloorGeometry,w:int):
    ok=bool(True)
    for g in range(s.geom_body.shape[0]):
        if floor_height(s,w,g)<s.bound[w,g]:ok=False
    return ok


@wp.kernel(enable_backward=False)
def guard(s:FloorGeometry,before:wp.array2d(dtype=float),after:wp.array2d(dtype=float),
          fractions:wp.array(dtype=float),blocked:wp.array(dtype=int)):
    w=wp.tid();changed=bool(False)
    for k in range(before.shape[1]):
        if before[w,k]!=after[w,k]:changed=True
    fractions[w]=1.
    if not changed:return
    floor_fk(s,before,after,w,0.)
    for g in range(s.geom_body.shape[0]):
        # At most 20 micrometres of geometric slop; never deepen existing
        # penetration. This is per-shape, not just the lowest body of the rig.
        s.bound[w,g]=wp.min(-2.e-5,floor_height(s,w,g))
    floor_fk(s,before,after,w,1.)
    if feasible(s,w):return
    blocked[w]+=1
    low=float(0.);high=float(1.);trial=float(.5)
    for _ in range(12):
        floor_fk(s,before,after,w,trial)
        if feasible(s,w):low=trial;break
        high=trial;trial*=.5
    if low>0.:
        for _ in range(8):
            mid=(low+high)*.5
            floor_fk(s,before,after,w,mid)
            if feasible(s,w):low=mid
            else:high=mid
    # Blend valid generalized coordinates; never interpolate quaternion signs
    # or modify the velocity solution from the contact/motor solver.
    for j in range(s.kind.shape[0]):
        qa=s.qadr[j];kind=s.kind[j]
        if kind==0:
            for k in range(3):after[w,qa+k]=(1.-low)*before[w,qa+k]+low*after[w,qa+k]
            rotation=blended_quat(before,after,w,qa+3,low)
            for k in range(4):after[w,qa+3+k]=rotation[k]
        elif kind==1:
            rotation=blended_quat(before,after,w,qa,low)
            for k in range(4):after[w,qa+k]=rotation[k]
        else:after[w,qa]=(1.-low)*before[w,qa]+low*after[w,qa]
    fractions[w]=low


class FloorProjectionGuard:
    def __init__(self,m,d,device,parallel=False):
        floors=np.flatnonzero((m.geom_type==0)&(m.geom_bodyid==0))
        if len(floors)!=1:raise ValueError('Floor projection guard requires one static plane')
        floor=int(floors[0])
        if not np.allclose(m.geom_quat[floor],[1.,0.,0.,0.],atol=1e-7):
            raise ValueError('Floor projection guard requires a horizontal Z-up plane')
        ids=np.flatnonzero((m.geom_bodyid>0)&((m.geom_contype!=0)|(m.geom_conaffinity!=0)))
        if not np.isin(m.geom_type[ids],[2,3,6]).all():raise ValueError('Unsupported floor collider shape')
        if np.any(m.body_mocapid>=0):raise ValueError('Mocap bodies unsupported in floor projection guard')
        s=FloorGeometry()
        for name,value,dtype in [('parent',m.body_parentid,int),('joint',m.body_jntadr,int),('joint_count',m.body_jntnum,int),
            ('body_pos',m.body_pos,wp.vec3),('body_quat',m.body_quat,wp.quat),('kind',m.jnt_type,int),
            ('qadr',m.jnt_qposadr,int),('anchor',m.jnt_pos,wp.vec3),('axis',m.jnt_axis,wp.vec3),('rest',m.qpos0,float),
            ('geom_body',m.geom_bodyid[ids],int),('geom_type',m.geom_type[ids],int),('geom_pos',m.geom_pos[ids],wp.vec3),
            ('geom_quat',m.geom_quat[ids],wp.quat),('geom_size',m.geom_size[ids],wp.vec3)]:
            setattr(s,name,wp.array(value,dtype=dtype,device=device))
        s.position=wp.empty((d.nworld,m.nbody),dtype=wp.vec3,device=device)
        s.rotation=wp.empty((d.nworld,m.nbody),dtype=wp.quat,device=device)
        s.bound=wp.empty((d.nworld,len(ids)),dtype=float,device=device);s.floor_z=float(m.geom_pos[floor,2])
        self.s=s;self.geom_ids=ids;self.before=wp.empty_like(d.qpos);self.data=d;self.device=device
        self.fractions=wp.ones(d.nworld,dtype=float,device=device)
        self.blocked=wp.zeros(d.nworld,dtype=int,device=device)
        self.parallel_apply=None
        if parallel:
            if len(ids)>32:raise ValueError('Parallel floor guard supports at most32 colliders')
            from floor_projection_parallel import apply_parallel
            self.parallel_apply=apply_parallel

    def save_before(self):wp.copy(self.before,self.data.qpos)

    def apply(self):
        if self.parallel_apply is not None:
            self.parallel_apply(self)
            return
        # Smaller blocks reduce divergence/register pressure in per-world FK
        # backtracking. Geometry and accepted corrections are unchanged.
        wp.launch(guard,dim=self.data.nworld,inputs=[self.s,self.before,self.data.qpos,self.fractions,self.blocked],device=self.device,block_dim=64)


guard.module.options['max_unroll']=1
