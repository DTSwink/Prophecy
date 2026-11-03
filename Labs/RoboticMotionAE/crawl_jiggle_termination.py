"""Sustained high-frequency hand reversals; isolated two-passive-leg crawl only."""
import torch

SPEC=dict(version=2,window_ticks=15,startup_grace_ticks=30,persistence_ticks=6,
          minimum_reversals=4,reversal_cosine=-.25,
          linear_cancellation_m_s=.08,angular_cancellation_rad_s=.8,
          minimum_linear_residual_m_s=.04,minimum_angular_residual_rad_s=.4,
          bodies=['right_hand','left_hand'],
          angular_bodies=['pelvis','torso','head','right_upper_arm','right_lower_arm','right_hand','left_upper_arm','left_lower_arm','left_hand'],scope='moving crawl, both legs disabled',
          definition='15-frame cancellation plus >=4 reversals around window mean on hands or upper-body rotation; six consecutive detections after 30-tick grace')

@torch.jit.script
def features(linear:torch.Tensor,angular:torch.Tensor):
    # [world,time,hand,xyz]. Remove drift ONLY when counting reversals.
    lm=linear.mean(1,keepdim=True);am=angular.mean(1,keepdim=True)
    lc=(linear.norm(p=2,dim=-1).mean(1)-lm[:,0].norm(p=2,dim=-1)).clamp_min(0.)
    ac=(angular.norm(p=2,dim=-1).mean(1)-am[:,0].norm(p=2,dim=-1)).clamp_min(0.)
    l=linear-lm;a=angular-am;ln=l.norm(p=2,dim=-1);an=a.norm(p=2,dim=-1)
    lr=(((l[:,1:]*l[:,:-1]).sum(-1)<-.25*ln[:,1:]*ln[:,:-1]) &
        (ln[:,1:]>.04)&(ln[:,:-1]>.04)).sum(1)
    ar=(((a[:,1:]*a[:,:-1]).sum(-1)<-.25*an[:,1:]*an[:,:-1]) &
        (an[:,1:]>.4)&(an[:,:-1]>.4)).sum(1)
    high=((lc>.08)&(lr>=4)).any(-1)|((ac>.8)&(ar>=4)).any(-1)
    return high,lc,ac,lr,ar

class JiggleTermination:
    def __init__(self,n,device,angular_body_count=9):
        self.linear=torch.zeros(n,15,2,3,device=device)
        self.angular=torch.zeros(n,15,angular_body_count,3,device=device)
        self.age=torch.zeros(n,dtype=torch.long,device=device)
        self.streak=torch.zeros_like(self.age)
        self.failed=torch.zeros(n,dtype=torch.bool,device=device)

    def reset(self,ids):
        self.linear[ids]=0.;self.angular[ids]=0.;self.age[ids]=0
        self.streak[ids]=0;self.failed[ids]=False

    def update(self,linear,angular,enabled):
        self.linear=torch.roll(self.linear,-1,1);self.angular=torch.roll(self.angular,-1,1)
        self.linear[:,-1]=linear;self.angular[:,-1]=angular;self.age.add_(1)
        high=features(self.linear,self.angular)[0] & (self.age>=30) & enabled
        self.streak.copy_(torch.where(high,self.streak+1,0))
        self.failed.copy_(self.streak>=6)
        return self.failed

def recorded_detection(pose,hand_ids,pelvis_id,fps,angular_body_ids=None):
    """Independent NumPy implementation, including warmup and persistence."""
    import numpy as np
    from scipy.spatial.transform import Rotation
    pos=pose[:,hand_ids,:3]-pose[:,pelvis_id:pelvis_id+1,:3]
    vel=np.diff(pos,axis=0)*fps
    angular_body_ids=hand_ids if angular_body_ids is None else angular_body_ids
    rot=pose[:,angular_body_ids,3:7]
    ang=(Rotation.from_quat(rot[1:].reshape(-1,4))*Rotation.from_quat(rot[:-1].reshape(-1,4)).inv()).as_rotvec().reshape(-1,len(angular_body_ids),3)*fps
    streak=np.zeros(len(pose),dtype=np.int64)
    for frame in range(30,len(pose)):
        high=False
        for values,minimum,threshold in ((vel,.04,.08),(ang,.4,.8)):
            z=values[frame-15:frame];mean=z.mean(0)
            cancellation=np.linalg.norm(z,axis=-1).mean(0)-np.linalg.norm(mean,axis=-1)
            residual=z-mean;n=np.linalg.norm(residual,axis=-1)
            rev=(((residual[1:]*residual[:-1]).sum(-1)<-.25*n[1:]*n[:-1]) &
                 (n[1:]>minimum)&(n[:-1]>minimum)).sum(0)
            high=high or bool(((cancellation>threshold)&(rev>=4)).any())
        streak[frame]=streak[frame-1]+1 if high else 0
    return streak>=6,streak
