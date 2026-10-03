"""Dodge-only active losses and normalized gated bank-request cost.

Sum travel across valid transitions, average the six normalized bank channels.
Pre-clamp requests retain a useful gradient at/after budget exhaustion; opposite
directions never cancel. Unbudgeted pelvis drop costs the same per metre
as horizontal pelvis movement, added to that channel without diluting others.
This does not modify any bank's application/clamping or checkpoint inputs.
"""
from dataclasses import dataclass,asdict
import torch
from transition_objective import Weights,Objective

LEGACY_BANK_LOSS_CONTRACT='six_normalized_gated_requests_preclamp_episode_sum_v1'
HALF_DROP_BANK_LOSS_CONTRACT='six_normalized_gated_requests_preclamp_plus_half_pelvis_drop_v2'
BANK_LOSS_CONTRACT='six_normalized_gated_requests_preclamp_plus_full_pelvis_drop_v3'
PELVIS_HEIGHT_CONTRACT='world_y_70cm_zero_30cm_one_valid_frame_mean_v1'
DIAGONAL_SLASHES=('slashRD','slashRU','slashLD','slashLU')
DIAGONAL_LOSS_CONTRACT='slashRD_RU_LD_LU_bank_x0p5_ccd_x1p5_v1'

def scale_diagonal_losses(loss,mask):
    """Scale per row, preserving raw diagnostics; replay frames match training."""
    for name,multiplier in (('bank_usage',.5),('ccd',1.5)):
        if name not in loss['weighted']:continue
        factor=torch.where(mask,multiplier,1.)
        loss['weighted'][name]=loss['weighted'][name]*factor
        if name in loss['frames']:loss['frames'][name]=loss['frames'][name]*factor[:,None]

@dataclass(frozen=True)
class BankedWeights(Weights):
    bank_usage: float=0.
    pelvis_height: float=0.
    ae_arms: float=0.
    elbow_pole: float=0.

def restart_weights(dodge,parry,bank_weight=0.):
    if dodge['kind']!='dodge' or parry['kind']!='parry' or not parry['full_arm_self_harm']:
        raise ValueError('Expected latest Dodge and full-arm Parry references')
    values=dict(dodge['weights'])
    for key in ('self_harm','left_hand_self_harm','forearm'):values[key]=parry['weights'][key]
    values.update(ccd=values['ccd']/10,calf=0.,required_block=0.,predictive_pin=0.,anti_pin_slide=0.,bank_usage=bank_weight)
    return BankedWeights(**values)

def bank_cost(requests,valid):
    if requests is None or requests.shape!=(*valid.shape,6):raise ValueError('Expected six bank requests per valid transition')
    frames=torch.where(valid,requests.mean(-1),0.)
    return frames.sum(-1),frames

def pelvis_height_cost(height,valid):
    """Actual world height, not requested bank motion; exclude primers/padding."""
    if height.shape!=valid.shape:raise ValueError('Height/mask shape mismatch')
    frames=torch.where(valid,((.70-height)/.40).clamp(0.,1.),0.)
    return frames.sum(-1)/valid.sum(-1).clamp_min(1),frames

class BankedObjective(Objective):
    def forward(self,result,episode):
        loss=super().forward(result,episode)
        if self.weights.elbow_pole>0:
            from dodge_elbow_pole import elbow_pole_cost
            cost,frames=elbow_pole_cost(result.positions[:,2:],self.skeleton.body_names,episode.valid[:,2:])
            loss['raw']['elbow_pole']=cost
            loss['weighted']['elbow_pole']=cost*self.weights.elbow_pole
            loss['frames']['elbow_pole']=frames
        if self.weights.ae_arms>0:
            from ae_arms import arms_cost
            cost,frames=arms_cost(self.arms_prior,result.rotations[:,2:],self.skeleton.body_names,episode.valid[:,2:])
            loss['raw']['ae_arms']=cost
            loss['weighted']['ae_arms']=cost*self.weights.ae_arms
            loss['frames']['ae_arms']=frames
        if self.weights.pelvis_height>0:
            index=self.skeleton.body_names.index('pelvis')
            cost,frames=pelvis_height_cost(result.positions[:,2:,index,1],episode.valid[:,2:])
            loss['raw']['pelvis_height']=cost
            loss['weighted']['pelvis_height']=cost*self.weights.pelvis_height
            loss['frames']['pelvis_height']=frames
        if getattr(self.weights,'bank_usage',0.)>0:
            cost,frames=bank_cost(result.bank_requests,episode.valid[:,2:])
            loss['raw']['bank_usage']=cost
            loss['weighted']['bank_usage']=cost*self.weights.bank_usage
            loss['frames']['bank_usage']=frames
        # Disabled terms are absent from training loss sums, TB and replay.
        for group in ('raw','weighted','frames'):
            loss[group]={k:v for k,v in loss[group].items() if getattr(self.weights,k,0.)>0}
        if getattr(self,'diagonal_loss_scaling',False):scale_diagonal_losses(loss,self.diagonal_slash_rows)
        loss['total']=sum(loss['weighted'].values()).mean()
        return loss
