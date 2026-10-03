"""Joint learned prior + existing geometry penalties; no pose/pin MSE.

Weights are explicit construction arguments: do not invent a calibration for
the new joint prior or required-block term. Labels select fixed priors/masks
only, and can never enter the VanillaDefense inference API.
"""
from dataclasses import dataclass
from pathlib import Path
import torch
from torch import nn
from transition_agents import native  # initializes the existing codec import paths
from conditional_delta_projector import ConditionalDeltaProjector
from defense_labels import RAW_TO_TYPE
from transition_features import SCHEMA, FEATURE_DIM, MOTION_DIM, freeze_prior, prior_score
from transition_geometry import defense_obbs,load_harness_geometry
from transition_collision import label_masks, harmful_contact_loss, required_block_contact, self_harm_loss
from transition_wrist import wrist_angular_velocity_frames
from transition_self_collision import SelfCollision


@dataclass(frozen=True)
class Weights:
    prior: float
    ccd: float
    calf: float
    forearm: float
    self_harm: float
    required_block: float
    wrist_angvel: float = 0.
    left_hand_self_harm: float = 0.
    leg_cross: float = 0.
    anti_statuing: float = 0.
    predictive_pin: float = 0.
    anti_pin_slide: float = 0.

    def __post_init__(self):
        import math
        if any(not math.isfinite(x) or x<0 for x in self.__dict__.values()):
            raise ValueError('Loss weights must be finite and nonnegative')


class FixedPrior(nn.Module):
    def __init__(self, model, mean, std):
        super().__init__();self.model=freeze_prior(model)
        if mean.shape!=(FEATURE_DIM,) or std.shape!=(FEATURE_DIM,):raise ValueError('Wrong prior normalization shape')
        if not bool(torch.isfinite(mean).all() & torch.isfinite(std).all() & (std>0).all()):
            raise ValueError('Invalid prior normalization')
        self.register_buffer('mean',mean);self.register_buffer('std',std)

    def forward(self,rows):return prior_score(self.model,rows,self.mean,self.std)


def load_prior(path,kind,device):
    checkpoint=torch.load(Path(path),map_location=device,weights_only=False)
    config=checkpoint['config']
    if (checkpoint['kind']!='defense_joint_conditional_transition_predictor_v1' or
        config['schema']!=SCHEMA or config['type']!=kind or
        config['input_dim']!=FEATURE_DIM or config['motion_dim']!=MOTION_DIM):
        raise ValueError('Incompatible joint-prior checkpoint')
    model=ConditionalDeltaProjector(FEATURE_DIM,MOTION_DIM,config['hidden_dim'],config['num_hidden_layers']).to(device)
    model.load_state_dict(checkpoint['model'],strict=True)
    return FixedPrior(model,checkpoint['mean'].to(device),checkpoint['std'].to(device))


def per_motion_mean(values,valid):
    return torch.where(valid,values,0.).sum(-1)/valid.sum(-1).clamp_min(1)


class Objective(nn.Module):
    @classmethod
    def from_cases(cls,kind,skeleton,cases,priors,weights,episode):
        """Production factory: harness-attested settings and exact attachments."""
        from harness_bindings import load
        geometry=load_harness_geometry(cases,episode.valid.device)
        local,active=load(cases,episode.valid.shape[1],episode.valid.device)
        times=None if kind=='dodge' else episode.times.new_tensor([
            case.record['diagnostics']['timing']['contact'] for case in cases])
        return cls(kind,skeleton,geometry,[int(case.data['motion_kind']) for case in cases],
            priors,weights,episode,times,local,active)

    def __init__(self,kind,skeleton,geometry,raw_kinds,priors,weights,episode,block_time=None,
                 foot_local=None,foot_override=None):
        super().__init__()
        if kind not in ('dodge','parry'):raise ValueError('Unknown defense training')
        if any((int(k)<16)!=(kind=='dodge') for k in raw_kinds):raise ValueError('Mixed independent trainings')
        if len(raw_kinds)!=episode.valid.shape[0]:raise ValueError('Label count differs from batch')
        self.kind=kind;self.skeleton=skeleton;self.geometry=geometry;self.weights=weights
        if any(int(k) in (22,23) for k in raw_kinds) and (foot_local is None or foot_override is None):
            raise ValueError('Leg-block training requires exact harness foot attachments; run harness_bindings.py')
        self.register_buffer('foot_local',foot_local);self.register_buffer('foot_override',foot_override)
        device=episode.valid.device
        present,blocking,harmful=label_masks(raw_kinds,geometry.names,device)
        self.register_buffer('present',present);self.register_buffer('blocking',blocking);self.register_buffer('harmful',harmful)
        types=[RAW_TO_TYPE[int(k)] for k in raw_kinds]
        wanted=sorted(set(types))
        if set(wanted)-set(priors):raise ValueError('A required trained prior is missing')
        self.priors=nn.ModuleDict({key:freeze_prior(priors[key]) for key in wanted})
        self.groups=[]
        for number,key in enumerate(wanted):
            name=f'group_{number}'
            self.register_buffer(name,torch.tensor([i for i,value in enumerate(types) if value==key],device=device))
            self.groups.append((key,name))
        self.register_buffer('clip_ids',torch.arange(len(raw_kinds),device=device))
        self.register_buffer('wrist_hand_indices',torch.tensor([skeleton.body_names.index('hand_'+side) for side in ('l','r')],device=device))
        self.register_buffer('wrist_forearm_indices',torch.tensor([skeleton.body_names.index('lowerarm_'+side) for side in ('l','r')],device=device))
        if kind=='parry':
            if block_time is None or block_time.shape!=(len(raw_kinds),):raise ValueError('Recorded block times required')
            last=episode.valid.sum(1)-1
            end=episode.times.gather(1,last[:,None]).squeeze(1)
            if not bool((torch.isfinite(block_time)&(block_time>=episode.times[:,1])&(block_time<=end)).all()):
                raise ValueError('Block event outside controlled, unpadded trajectory')
        elif block_time is not None or weights.required_block!=0:
            raise ValueError('Dodge has no required-block objective')
        self.register_buffer('block_time',block_time)
        self.self_collision=SelfCollision(geometry) if weights.left_hand_self_harm>0 or weights.leg_cross>0 else None
        self.pin_foot_indices=tuple(skeleton.body_names.index('foot_'+s) for s in ('l','r'))
        self.pin_toe_indices=tuple(skeleton.body_names.index('ball_'+s) for s in ('l','r'))

    def foot_terms(self,result,episode,include_slide=False):
        from transition_foot_pin import insufficient_pin,symmetric_pin,anti_pin_slide,checkpoint_pin_loss_contract,SYMMETRIC_PIN_LOSS_CONTRACT
        from transition_agents import LINEAR_PIN_MODE,LEGACY_PIN_MODE
        valid=episode.valid[:,2:]
        expected=self.pin_teacher.expected(result.predictor_rows)
        contract=checkpoint_pin_loss_contract(dict(
            pin_command_mode=getattr(self,'pin_command_mode',LEGACY_PIN_MODE),
            pin_loss_contract=getattr(self,'pin_loss_contract',None)))
        if getattr(self,'pin_command_mode',LEGACY_PIN_MODE)==LINEAR_PIN_MODE:
            if result.pin_commands is None:raise ValueError('Raw commands required for predictive pin loss')
            loss_fn=symmetric_pin if contract==SYMMETRIC_PIN_LOSS_CONTRACT else insufficient_pin
            pin=loss_fn(expected,result.pin_commands)
        else:
            # Historical checkpoints retain their original objective too.
            pin=insufficient_pin(expected,result.pin_probabilities)
        slide=torch.zeros_like(pin);speed_squared=ramp=None
        if include_slide:
            slide,speed_squared,ramp=anti_pin_slide(result.positions,episode.times,result.pin_probabilities,
                self.pin_foot_indices,self.pin_toe_indices,valid)
        return dict(predictive_pin=pin,anti_pin_slide=slide,expected=expected,speed_squared=speed_squared,ramp=ramp)

    def forward(self,result,episode):
        valid=episode.valid[:,2:];batch,frames=valid.shape
        scores=result.predictor_rows.new_zeros((batch,frames))
        # Fixed groups, one batched prior call per type, no dynamic nonzero,
        # no scoring other labels, no repeated prior calls per time step.
        if hasattr(self,'routed_prior'):
            scores=self.routed_prior(result.predictor_rows,self.prior_type_ids)
        else:
            for kind,name in self.groups:
                indices=getattr(self,name)
                selected=result.predictor_rows.index_select(0,indices)
                values=self.priors[kind](selected.reshape(-1,FEATURE_DIM)).reshape(indices.numel(),frames)
                scores=scores.index_copy(0,indices,values)
        statue=torch.zeros_like(scores)
        if self.weights.anti_statuing>0:
            if not hasattr(self,'routed_statue'):raise ValueError('Missing anti-statuing models')
            statue=self.routed_statue(result.predictor_rows,self.prior_type_ids)
        foot=None;predictive_pin=torch.zeros_like(scores);anti_pin_slide=torch.zeros_like(scores)
        if self.weights.predictive_pin>0 or self.weights.anti_pin_slide>0:
            if not hasattr(self,'pin_teacher'):raise ValueError('Missing foot pin predictor')
            foot=self.foot_terms(result,episode,include_slide=self.weights.anti_pin_slide>0)
            predictive_pin=foot['predictive_pin'];anti_pin_slide=foot['anti_pin_slide']
        calf=torch.zeros_like(scores)
        if self.weights.calf>0:
            calf,_=native.calf_length_error_frames(self.skeleton,result.positions[:,2:],self.clip_ids)
        forearm,_=native.lowerarm_length_error_frames(self.skeleton,result.positions[:,2:],self.clip_ids)
        full_centers,full_axes=defense_obbs(result.positions,result.rotations,self.geometry,
            self.foot_local,self.foot_override)
        centers,axes=full_centers[:,1:],full_axes[:,1:]
        attack=episode.collider[:,1:,:3];attack_axes=episode.collider_axes[:,1:]
        ccd,events=harmful_contact_loss(centers,axes,attack,attack_axes,episode.attack_half,
            self.geometry,self.blocking,self.harmful,valid,
            all_contacts=self.kind=='dodge' and getattr(self,'all_contacts_ccd',False))
        full_arms=getattr(self,'full_arm_self_harm',False)
        self_harm=self_harm_loss(centers,axes,self.geometry,self.present,valid,include_right_forearm=not full_arms,
            blade_body_indices=getattr(self.self_collision,'blade_body_indices',None))
        required=ccd.new_zeros(ccd.shape)
        if self.kind=='parry':
            required=required_block_contact(centers,axes,attack,attack_axes,episode.attack_half,
                self.geometry,self.blocking,episode.times[:,1:],self.block_time)
        wrist=scores.new_zeros(scores.shape)
        if self.weights.wrist_angvel>0:
            _,wrist=wrist_angular_velocity_frames(result.rotations,episode.times,
                self.wrist_hand_indices,self.wrist_forearm_indices,valid)
        self_contacts=None;hand=torch.zeros_like(scores);legs=torch.zeros_like(scores)
        if self.self_collision is not None:
            self_contacts=self.self_collision(result.positions,result.rotations,full_centers,full_axes,valid)
            hand=self_contacts['left_hand_self_harm'];legs=self_contacts['leg_cross']
            if full_arms:self_harm=self_harm+self_contacts['right_arm_self_harm']
        raw=dict(prior=per_motion_mean(scores,valid),ccd=ccd,calf=per_motion_mean(calf,valid),
            forearm=per_motion_mean(forearm,valid),self_harm=per_motion_mean(self_harm,valid),
            required_block=required,wrist_angvel=per_motion_mean(wrist,valid),
            left_hand_self_harm=per_motion_mean(hand,valid),leg_cross=per_motion_mean(legs,valid),
            anti_statuing=per_motion_mean(statue,valid),predictive_pin=per_motion_mean(predictive_pin,valid),
            anti_pin_slide=per_motion_mean(anti_pin_slide,valid))
        weighted={key:value*getattr(self.weights,key) for key,value in raw.items()}
        total=sum(weighted.values()).mean()
        output=dict(total=total,raw=raw,weighted=weighted,events=events,
                    colliders=(full_centers,full_axes),
                    self_contacts=self_contacts,
                    foot_pin=foot,
                    frames=dict(prior=scores,calf=calf,forearm=forearm,self_harm=self_harm,wrist_angvel=wrist,
                        left_hand_self_harm=hand,leg_cross=legs,anti_statuing=statue,
                        predictive_pin=predictive_pin,anti_pin_slide=anti_pin_slide))
        if events.interval_loss is not None:output['frames']['ccd']=events.interval_loss
        return output
