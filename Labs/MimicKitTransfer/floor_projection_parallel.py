"""Parallel implementation of the floor feasibility guard.
One warp per world and one GPU lane per collider, with ancestor-chain FK.
Scalar implementation remains an independent diagnostic reference.
"""
import warp as wp
from mujoco_warp._src import math as mm
from floor_projection_guard import FloorGeometry,blended_quat

@wp.func
def chain_height(s:FloorGeometry,a:wp.array2d(dtype=float),b:wp.array2d(dtype=float),w:int,t:float,g:int):
    if g>=s.geom_body.shape[0]:return float(1.e10)
    pos=s.geom_pos[g];rot=s.geom_quat[g];body=s.geom_body[g]
    while body>0:
        local_pos=s.body_pos[body];local_rot=s.body_quat[body]
        for offset in range(s.joint_count[body]):
            idx=s.joint[body]+offset;qa=s.qadr[idx];kind=s.kind[idx]
            if kind==0:
                local_pos=wp.vec3((1.-t)*a[w,qa]+t*b[w,qa],(1.-t)*a[w,qa+1]+t*b[w,qa+1],(1.-t)*a[w,qa+2]+t*b[w,qa+2])
                local_rot=blended_quat(a,b,w,qa+3,t)
            else:
                anchor=local_pos+mm.rot_vec_quat(s.anchor[idx],local_rot)
                if kind==1:
                    local_rot=mm.mul_quat(local_rot,blended_quat(a,b,w,qa,t))
                    local_pos=anchor-mm.rot_vec_quat(s.anchor[idx],local_rot)
                elif kind==3:
                    angle=(1.-t)*a[w,qa]+t*b[w,qa]-s.rest[qa]
                    local_rot=mm.mul_quat(local_rot,mm.axis_angle_to_quat(s.axis[idx],angle))
                    local_pos=anchor-mm.rot_vec_quat(s.anchor[idx],local_rot)
                elif kind==2:
                    local_pos+=mm.rot_vec_quat(s.axis[idx],local_rot)*((1.-t)*a[w,qa]+t*b[w,qa]-s.rest[qa])
        local_rot=wp.normalize(local_rot)
        pos=local_pos+mm.rot_vec_quat(pos,local_rot)
        rot=mm.mul_quat(local_rot,rot);body=s.parent[body]
    size=s.geom_size[g];extent=size[0]
    if s.geom_type[g]==3:extent+=size[1]*wp.abs(mm.rot_vec_quat(wp.vec3(0.,0.,1.),rot)[2])
    elif s.geom_type[g]==6:
        extent=wp.abs(mm.rot_vec_quat(wp.vec3(size[0],0.,0.),rot)[2])+wp.abs(mm.rot_vec_quat(wp.vec3(0.,size[1],0.),rot)[2])+wp.abs(mm.rot_vec_quat(wp.vec3(0.,0.,size[2]),rot)[2])
    return pos[2]-extent-s.floor_z

@wp.kernel(enable_backward=False)
def parallel_guard(s:FloorGeometry,before:wp.array2d(dtype=float),after:wp.array2d(dtype=float),fractions:wp.array(dtype=float),blocked:wp.array(dtype=int)):
    w,lane=wp.tid();changed=int(0)
    for k in range(lane,before.shape[1],32):
        if before[w,k]!=after[w,k]:changed=1
    any_changed=wp.tile_extract(wp.tile_sum(wp.tile(changed)),0)
    if lane==0:fractions[w]=1.
    if any_changed==0:return
    bound=wp.min(-2.e-5,chain_height(s,before,after,w,0.,lane))
    height=chain_height(s,before,after,w,1.,lane)
    violation=int(height<bound)
    if wp.tile_extract(wp.tile_sum(wp.tile(violation)),0)==0:return
    if lane==0:blocked[w]+=1
    low=float(0.);high=float(1.);trial=float(.5)
    for _ in range(12):
        height=chain_height(s,before,after,w,trial,lane)
        violation=int(height<bound)
        if wp.tile_extract(wp.tile_sum(wp.tile(violation)),0)==0:
            low=trial;break
        high=trial;trial*=.5
    if low>0.:
        for _ in range(8):
            mid=(low+high)*.5
            violation=int(chain_height(s,before,after,w,mid,lane)<bound)
            if wp.tile_extract(wp.tile_sum(wp.tile(violation)),0)==0:low=mid
            else:high=mid
    for j in range(lane,s.kind.shape[0],32):
        qa=s.qadr[j];kind=s.kind[j]
        if kind==0:
            for k in range(3):after[w,qa+k]=(1.-low)*before[w,qa+k]+low*after[w,qa+k]
            rotation=blended_quat(before,after,w,qa+3,low)
            for k in range(4):after[w,qa+3+k]=rotation[k]
        elif kind==1:
            rotation=blended_quat(before,after,w,qa,low)
            for k in range(4):after[w,qa+k]=rotation[k]
        else:after[w,qa]=(1.-low)*before[w,qa]+low*after[w,qa]
    if lane==0:fractions[w]=low

parallel_guard.module.options['max_unroll']=1

def apply_parallel(self):
    if self.s.geom_body.shape[0]>32:
        raise ValueError('Parallel guard supports at most32 colliders')
    wp.launch(parallel_guard,dim=(self.data.nworld,32),inputs=[self.s,self.before,self.data.qpos,self.fractions,self.blocked],device=self.device,block_dim=32)
