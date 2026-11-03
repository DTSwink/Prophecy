"""Six-frame hand velocity cancellation, charged outside the pose exponential."""
import torch
from util import torch_util as q

SPEC=dict(version=1,window_ticks=6,linear_tolerance_m_s=.05,angular_tolerance_rad_s=1.,
          linear_scale_m_s=.1,angular_scale_rad_s=2.,coefficient=9.,maximum=5.,
          bodies=['right_hand','left_hand'],form='velocity_cancellation_v1',
          definition='min(5, 9 * mean_hands((relu(linear_cancellation-.05)/.1)^2 + (relu(angular_cancellation-1)/2)^2)); subtract outside exp(-pose_loss)')

@torch.jit.script
def cancellation_cost(linear:torch.Tensor,angular:torch.Tensor):
    # [world, time, hand, xyz]; constant or consistently directed motion cancels to zero.
    lc=(torch.linalg.vector_norm(linear,dim=-1).mean(1)-torch.linalg.vector_norm(linear.mean(1),dim=-1)).clamp_min(0.)
    ac=(torch.linalg.vector_norm(angular,dim=-1).mean(1)-torch.linalg.vector_norm(angular.mean(1),dim=-1)).clamp_min(0.)
    cost=9.*(((lc-.05).clamp_min(0.)/.1).square()+((ac-1.).clamp_min(0.)/2.).square()).mean(-1)
    # gamma=.99, failure=500: discounted nonterminal cost cannot exceed 500.
    return cost.clamp_max(5.),lc.mean(-1),ac.mean(-1)

class HandJiggle:
    def __init__(self,n,device):
        self.linear=torch.zeros(n,6,2,3,device=device)
        self.angular=torch.zeros_like(self.linear)
        self.previous_pos=torch.zeros(n,2,3,device=device)
        self.previous_rot=torch.zeros(n,2,4,device=device);self.previous_rot[:,:,3]=1.
        self.count=torch.zeros(n,dtype=torch.long,device=device)

    def reset(self,ids,pos,rot):
        self.linear[ids]=0.;self.angular[ids]=0.;self.count[ids]=0
        self.previous_pos[ids]=pos;self.previous_rot[ids]=rot

    def update(self,pos,rot,dt):
        velocity=(pos-self.previous_pos)/dt
        omega=q.quat_to_exp_map(q.quat_mul(rot,q.quat_conjugate(self.previous_rot)))/dt
        self.linear=torch.roll(self.linear,-1,1);self.angular=torch.roll(self.angular,-1,1)
        self.linear[:,-1]=velocity;self.angular[:,-1]=omega
        self.previous_pos.copy_(pos);self.previous_rot.copy_(rot);self.count.add_(1)
        cost,lc,ac=cancellation_cost(self.linear,self.angular)
        ready=self.count>=6
        return torch.where(ready,cost,0.),torch.where(ready,lc,0.),torch.where(ready,ac,0.)

def recorded_cost(pose,hand_ids,pelvis_id,fps):
    """Independent NumPy/SciPy implementation for saved rollout verification."""
    import numpy as np
    from scipy.spatial.transform import Rotation
    p=pose[:,hand_ids,:3]-pose[:,pelvis_id:pelvis_id+1,:3]
    v=np.diff(p,axis=0)*fps
    quat=pose[:,hand_ids,3:7]
    rot=Rotation.from_quat(quat.reshape(-1,4))
    quat=rot.as_quat().reshape(-1,2,4)
    a=(Rotation.from_quat(quat[1:].reshape(-1,4))*Rotation.from_quat(quat[:-1].reshape(-1,4)).inv()).as_rotvec().reshape(-1,2,3)*fps
    out=np.zeros(len(pose))
    for frame in range(6,len(pose)):
        vv=v[frame-6:frame];aa=a[frame-6:frame]
        lc=np.linalg.norm(vv,axis=-1).mean(0)-np.linalg.norm(vv.mean(0),axis=-1)
        ac=np.linalg.norm(aa,axis=-1).mean(0)-np.linalg.norm(aa.mean(0),axis=-1)
        out[frame]=min(5.,9.*np.mean((np.maximum(lc-.05,0)/.1)**2+(np.maximum(ac-1.,0)/2.)**2))
    return out
