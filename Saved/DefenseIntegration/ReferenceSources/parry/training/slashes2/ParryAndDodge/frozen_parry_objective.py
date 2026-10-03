"""Upper-channel priors, free contact timing, unchanged geometric penalties."""
import torch
from torch import nn
from transition_agents import native
from transition_objective import per_motion_mean
from transition_geometry import defense_obbs
from transition_collision import label_masks,self_harm_loss
from transition_self_collision import SelfCollision
from transition_wrist import wrist_angular_velocity_frames
from frozen_parry_collision import free_contact_objective
from frozen_parry_blade_plane import contact_plane_loss
from frozen_parry_blade_center import contact_center_loss,attacker_center_loss
from frozen_parry_blade_velocity import blade_velocity_loss
from frozen_parry_attacker_edge import attacker_edge_loss
from frozen_parry_block_clearance import block_clearance_loss
from frozen_parry_early_contact import early_contact_loss
from frozen_parry_forearm_center import forearm_center_loss
from frozen_parry_upperarm_zone import UpperArmZone
from frozen_parry_forearm_direction import ForearmDirection
from frozen_parry_contact_target import contact_target_loss
from frozen_parry_behind_chest import BehindChest
from frozen_parry_elbow_pole import NonBlockingElbowPole
from frozen_parry_spine_yaw import SpineYaw
from frozen_parry_spine_tilt import SpineTilt
from frozen_parry_upperarm_inward import UpperArmInward
from frozen_parry_gaze import Gaze
from frozen_parry_control_smoothness import ControlSmoothness
from frozen_parry_spine_limits import SpineLimits
from frozen_parry_free_hand_idle import FreeHandIdle
from frozen_parry_success_self_harm import SuccessSelfHarm
from attacker_pelvis_cylinder import AttackerPelvisCylinder


def upper_block_masks(raw,names,device,drawn=None):
    present,blocking,harmful=label_masks(raw,names,device)
    if drawn is not None:
        present[:,names.index('blade')]=torch.as_tensor(drawn,device=device).bool()
        blocking=blocking & present
    for row,kind in enumerate(raw):
        if kind in (22,23):
            side='l' if kind==22 else 'r'
            blocking[row]=torch.tensor([name in tuple(b+'_'+side for b in ('upperarm','lowerarm','hand'))
                for name in names],device=device)&present[row]
    return present,blocking,present&~blocking


class UpperObjective(nn.Module):
    free_contact_timing = True
    def __init__(self,skeleton,geometry,raw,weights,episode,prior,statue,prior_type_ids,block_time=None,full_arm_self_harm=False):
        super().__init__();self.kind='parry';self.skeleton=skeleton;self.geometry=geometry;self.weights=weights
        if weights.predictive_pin!=0 or weights.anti_pin_slide!=0:raise ValueError('Frozen foot-pin losses must be disabled')
        self.routed_prior=prior;self.routed_statue=statue
        self.register_buffer('block_time',block_time)
        self.register_buffer('attacker_hit_time',None)
        self.required_block_timing='free' if block_time is None else 'authored_or_previous'
        for key,value in zip(('present','blocking','harmful'),upper_block_masks(raw,geometry.names,episode.valid.device)):
            self.register_buffer(key,value)
        self.register_buffer('prior_type_ids',prior_type_ids)
        self.register_buffer('clip_ids',torch.arange(len(raw),device=episode.valid.device))
        self.register_buffer('wrist_hand_indices',torch.tensor([skeleton.body_names.index('hand_'+s) for s in ('l','r')],device=episode.valid.device))
        self.register_buffer('wrist_forearm_indices',torch.tensor([skeleton.body_names.index('lowerarm_'+s) for s in ('l','r')],device=episode.valid.device))
        self.full_arm_self_harm=full_arm_self_harm
        self.blade_index=geometry.names.index('blade')
        self.upperarm_zone=UpperArmZone(skeleton.body_names)
        self.forearm_direction=ForearmDirection(skeleton.body_names)
        self.behind_chest=BehindChest(skeleton.body_names,geometry)
        self.elbow_pole=NonBlockingElbowPole(skeleton.body_names,geometry.names)
        self.spine_yaw=SpineYaw(skeleton.body_names)
        self.spine_tilt=SpineTilt(skeleton.body_names)
        self.upperarm_inward=UpperArmInward(skeleton.body_names)
        self.gaze=Gaze(skeleton.body_names)
        self.control_smoothness=ControlSmoothness(skeleton).to(episode.valid.device)
        self.spine_limits=SpineLimits(skeleton).to(episode.valid.device)
        self.free_hand_idle=FreeHandIdle(skeleton).to(episode.valid.device)
        self.success_self_harm=SuccessSelfHarm(geometry)
        self.attacker_pelvis_cylinder=AttackerPelvisCylinder(geometry)
        self.register_buffer('self_blade_body_indices',torch.tensor(
            [i for i in geometry.self_body_indices.tolist() if not geometry.names[i].startswith('upperarm_')],
            device=episode.valid.device,dtype=torch.long))
        self.register_buffer('blade_plane_normals',None)
        self.register_buffer('blade_plane_valid',None)
        self.self_collision=SelfCollision(geometry,full_arms=full_arm_self_harm,exclude_upperarms=full_arm_self_harm) if weights.left_hand_self_harm>0 or weights.leg_cross>0 or (full_arm_self_harm and weights.self_harm>0) else None

    def forward(self,result,episode):
        centers,axes=defense_obbs(result.positions,result.rotations,self.geometry)
        contact=free_contact_objective(centers[:,1:],axes[:,1:],episode.collider[:,1:,:3],
            episode.collider_axes[:,1:],episode.attack_half,self.geometry,self.blocking,self.harmful,
            episode.valid[:,2:],times=episode.times[:,1:],block_time=self.block_time)
        valid=contact['interval_valid']
        cylinder_penalty,attacker_cylinder=self.attacker_pelvis_cylinder(
            result.positions,centers,axes,episode,contact['events'],self.present,valid)
        scores=self.routed_prior(result.predictor_rows,self.prior_type_ids)
        statue=self.routed_statue(result.predictor_rows,self.prior_type_ids) if self.weights.anti_statuing>0 else torch.zeros_like(scores)
        calf=torch.zeros_like(scores)
        if self.weights.calf>0:
            calf,_=native.calf_length_error_frames(self.skeleton,result.positions[:,2:],self.clip_ids)
        forearm,_=native.lowerarm_length_error_frames(self.skeleton,result.positions[:,2:],self.clip_ids)
        harm=self_harm_loss(centers[:,1:],axes[:,1:],self.geometry,self.present,valid,
            include_right_forearm=not self.full_arm_self_harm,blade_body_indices=self.self_blade_body_indices)
        wrist=torch.zeros_like(scores)
        if self.weights.wrist_angvel>0:
            _,wrist=wrist_angular_velocity_frames(result.rotations,episode.times,self.wrist_hand_indices,self.wrist_forearm_indices,valid)
        hand=torch.zeros_like(scores);legs=torch.zeros_like(scores);self_contacts=None
        if self.self_collision is not None:
            self_contacts=self.self_collision(result.positions,result.rotations,centers,axes,valid)
            hand=self_contacts['left_hand_self_harm'];legs=self_contacts['leg_cross']
            if self.full_arm_self_harm:harm=harm+self_contacts['right_arm_self_harm']
        # Preserve existing loss routing: blade/right chain under self_harm,
        # left hand/forearm under left_hand_self_harm. Upperarms stay excluded.
        harm=harm+cylinder_penalty[...,0]+cylinder_penalty[...,1:3].amax(-1)
        hand=hand+cylinder_penalty[...,3:5].amax(-1)
        zero=torch.zeros_like(scores)
        upperarm_zone=(self.upperarm_zone(result.positions[:,2:],result.rotations[:,2:]).mean(-1)
            if self.weights.upperarm_zone>0 else zero)
        forearm_direction=(self.forearm_direction(result.positions[:,2:],result.rotations[:,2:]).mean(-1)
            if self.weights.forearm_direction>0 else zero)
        frames=dict(prior=scores,anti_statuing=statue,calf=calf,forearm=forearm,self_harm=harm,
            wrist_angvel=wrist,left_hand_self_harm=hand,leg_cross=legs,predictive_pin=zero,anti_pin_slide=zero,
            upperarm_zone=upperarm_zone,forearm_direction=forearm_direction)
        frames['behind_chest'],behind_chest=self.behind_chest(result.positions[:,2:],result.rotations[:,2:],centers[:,2:],axes[:,2:],self.present,self.blocking)
        frames['elbow_pole'],elbow_pole=self.elbow_pole(result.positions[:,2:],self.blocking)
        frames['spine_yaw'],spine_yaw=self.spine_yaw(result.positions[:,2:],result.rotations[:,2:],episode.pelvis[:,2:],episode.attack_type,episode.collider,episode.collider_axes,episode.attack_half)
        inward_scores,upperarm_inward=self.upperarm_inward(result.positions[:,2:],result.rotations[:,2:])
        frames['upperarm_inward']=inward_scores.mean(-1)
        frames['spine_tilt'],spine_tilt=self.spine_tilt(result.rotations[:,2:])
        frames['gaze'],gaze=self.gaze(result.positions[:,2:],result.rotations[:,2:],episode.collider[:,2:,:3])
        frames['control_smoothness']=self.control_smoothness(result,episode.times,valid)
        _,frames['spine_angvel']=self.spine_limits(result.rotations,episode.times,valid)
        frames['free_hand_idle']=self.free_hand_idle(result.rotations[:,2:],self.present[:,self.blade_index])
        raw={key:per_motion_mean(value,valid) for key,value in frames.items()}
        raw.update(ccd=contact['ccd'],required_block=contact['required_block'])
        blade_plane=None
        if self.blade_plane_normals is not None:
            raw['blade_plane'],blade_plane=contact_plane_loss(axes,contact['events'],
                self.blade_plane_normals,self.blade_plane_valid,self.blade_index,episode,self.blocking)
        raw['blade_center'],blade_center=contact_center_loss(centers,axes,episode,contact['events'],self.geometry,self.blocking)
        raw['attacker_blade_center'],attacker_blade_center=attacker_center_loss(blade_center)
        raw['blade_velocity'],blade_velocity=blade_velocity_loss(centers,episode,contact['events'],self.geometry,blade_center)
        raw['attacker_edge'],attacker_edge=attacker_edge_loss(centers,axes,episode,self.geometry,blade_center)
        raw['block_clearance'],block_clearance=block_clearance_loss(
            centers,axes,episode,contact['events'],self.geometry,self.present,self.blocking)
        early_contact=None
        if self.attacker_hit_time is not None:
            raw['early_contact'],early_contact=early_contact_loss(
                centers,axes,episode,contact['events'],self.geometry,self.blocking,self.attacker_hit_time)
        elif self.weights.early_contact>0:raise ValueError('Early contact loss requires attacker hit metadata')
        raw['success_self_harm'],success_self_harm=self.success_self_harm(
            centers,axes,episode,contact['events'],self.present,self.blocking,cylinder_penalty[...,:3])
        raw['forearm_center'],forearm_center=forearm_center_loss(centers,axes,episode,contact['events'],
            self.geometry,self.blocking,self.present[:,self.blade_index])
        raw['contact_target'],contact_target=contact_target_loss(
            centers,axes,episode,contact['events'],self.geometry,self.blocking)
        weighted={key:value*getattr(self.weights,key,0.) for key,value in raw.items()}
        return dict(total=sum(weighted.values()).mean(),raw=raw,weighted=weighted,frames=frames,
            events=contact['events'],colliders=(centers,axes),self_contacts=self_contacts,foot_pin=None,attacker_cylinder=attacker_cylinder,
            terminal_frame=contact['terminal_frame']+1,interval_valid=valid,contact=contact,blade_plane=blade_plane,blade_velocity=blade_velocity,attacker_edge=attacker_edge,
            early_contact=early_contact,block_clearance=block_clearance,blade_center=blade_center,attacker_blade_center=attacker_blade_center,forearm_center=forearm_center,contact_target=contact_target,behind_chest=behind_chest,elbow_pole=elbow_pole,spine_yaw=spine_yaw,upperarm_inward=upperarm_inward,success_self_harm=success_self_harm)
