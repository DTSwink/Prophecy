"""Inference-only FK in one GPU launch; same hierarchy and quaternion algebra.

The upstream method remains available for CPU/autograd and comparisons. Each
call owns its outputs: later reference updates cannot overwrite an earlier pose.
"""
import torch
import warp as wp


@wp.func
def multiply(a: wp.vec4, b: wp.vec4):
    x1,y1,z1,w1=a[0],a[1],a[2],a[3]
    x2,y2,z2,w2=b[0],b[1],b[2],b[3]
    ww=(z1+x1)*(x2+y2)
    yy=(w1-y1)*(w2+z2)
    zz=(w1+y1)*(w2-z2)
    xx=ww+yy+zz
    qq=0.5*(xx+(z1-x1)*(x2-y2))
    return wp.vec4(qq-xx+(x1+w1)*(x2+w2),qq-yy+(w1-x1)*(y2+z2),
                   qq-zz+(z1+y1)*(w2-x2),qq-ww+(z1-y1)*(y2-z2))


@wp.kernel(enable_backward=False)
def fk(root_pos: wp.array(dtype=wp.vec3), root_rot: wp.array(dtype=wp.vec4),
       joint_rot: wp.array2d(dtype=wp.vec4), parents: wp.array(dtype=int),
       local_pos: wp.array(dtype=wp.vec3), local_rot: wp.array(dtype=wp.vec4),
       pos: wp.array2d(dtype=wp.vec3), rot: wp.array2d(dtype=wp.vec4)):
    row=wp.tid()
    pos[row,0]=root_pos[row];rot[row,0]=root_rot[row]
    for j in range(1,parents.shape[0]):
        parent=parents[j];r=rot[row,parent];v=local_pos[j]
        xyz=wp.vec3(r[0],r[1],r[2]);t=2.0*wp.cross(xyz,v)
        pos[row,j]=pos[row,parent]+(v+r[3]*t+wp.cross(xyz,t))
        rot[row,j]=multiply(r,multiply(local_rot[j],joint_rot[row,j-1]))


wp.set_module_options({'enable_backward':False,'enable_mathdx_gemm':False,'fuse_fp':False})


class FusedKinematics:
    def __init__(self, model):
        self.reference=model.forward_kinematics
        self.count=model.get_num_joints()
        parents=model._parent_indices
        if any(not 0 <= parents[j] < j for j in range(1,self.count)):
            raise ValueError('FK requires parent-before-child ordering')
        self.parents=wp.array(parents,dtype=int,device=str(model._device))
        self.local_pos=wp.from_torch(model._local_translation,dtype=wp.vec3)
        self.local_rot=wp.from_torch(model._local_rotation,dtype=wp.vec4)

    def __call__(self, root_pos, root_rot, joint_rot):
        inputs=(root_pos,root_rot,joint_rot)
        if (not root_pos.is_cuda or any(x.dtype != torch.float32 for x in inputs)
                or (torch.is_grad_enabled() and any(x.requires_grad for x in inputs))):
            return self.reference(*inputs)
        shape=root_pos.shape[:-1]
        root_pos=root_pos.reshape(-1,3).contiguous()
        root_rot=root_rot.reshape(-1,4).contiguous()
        joint_rot=joint_rot.reshape(-1,self.count-1,4).contiguous()
        pos=torch.empty((*shape,self.count,3),device=root_pos.device)
        rot=torch.empty((*shape,self.count,4),device=root_pos.device)
        if root_pos.shape[0]:
            wp.launch(fk,dim=root_pos.shape[0],inputs=[
                wp.from_torch(root_pos,dtype=wp.vec3),wp.from_torch(root_rot,dtype=wp.vec4),
                wp.from_torch(joint_rot,dtype=wp.vec4),self.parents,self.local_pos,self.local_rot,
                wp.from_torch(pos.reshape(-1,self.count,3),dtype=wp.vec3),
                wp.from_torch(rot.reshape(-1,self.count,4),dtype=wp.vec4)],
                stream=wp.stream_from_torch(torch.cuda.current_stream(root_pos.device)))
        return pos,rot


def install(model):
    if not isinstance(model.forward_kinematics,FusedKinematics):
        model.forward_kinematics=FusedKinematics(model)
