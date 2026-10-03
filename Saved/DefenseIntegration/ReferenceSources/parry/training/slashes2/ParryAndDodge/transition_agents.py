"""Vanilla lower -> upper inference shared by new defense training/export.

No frozen checkpoint can be passed to this API. Root command is initialized
from the two primers and persists as a world vector; only its current-root
expression changes. Native pins and the existing skeleton codec are reused.
"""
from dataclasses import dataclass
from pathlib import Path
import sys
import torch

ROOT=Path(__file__).resolve().parents[1]
for directory in (ROOT,ROOT/'DefenseHarness'):sys.path.insert(0,str(directory))
import train_imitation_smoke as native
import train_slash_controller as slash
import transition_features as features

CHECKPOINT_KIND='defense_vanilla_joint_prior_initial_root_v1'
LEGACY_PIN_MODE='centered_sigmoid_clamp_v1'
LINEAR_PIN_MODE='linear_clamp_v1'
PIN_MODES=(LEGACY_PIN_MODE,LINEAR_PIN_MODE)


def checkpoint_pin_mode(config):
    mode=config.get('pin_command_mode',LEGACY_PIN_MODE)
    if mode not in PIN_MODES:raise ValueError('Unknown checkpoint pin-command mapping')
    return mode


@dataclass
class State:
    previous_lower: torch.Tensor
    previous_upper: torch.Tensor
    current_lower: torch.Tensor
    current_upper: torch.Tensor
    previous_root: torch.Tensor
    previous_axes: torch.Tensor
    current_root: torch.Tensor
    current_axes: torch.Tensor
    initial_axes: torch.Tensor
    initial_delta_world: torch.Tensor
    initial_delta_yaw: torch.Tensor


@dataclass
class Proposal:
    state: State
    positions: torch.Tensor
    rotations: torch.Tensor
    predictor_row: torch.Tensor
    pin_probabilities: torch.Tensor
    lower_output: torch.Tensor
    upper_output: torch.Tensor
    bank_requests: torch.Tensor | None = None


class VanillaDefense(torch.nn.Module):
    def __init__(self,kind,skeleton,recipe=None,*,pin_command_mode=LEGACY_PIN_MODE):
        super().__init__()
        if kind not in ('dodge','parry'):raise ValueError('Choose one independent defense training')
        if pin_command_mode not in PIN_MODES:raise ValueError('Unknown pin-command mapping')
        self.kind=kind;self.skeleton=skeleton;self.pin_command_mode=pin_command_mode
        recipe=recipe or slash.Recipe()
        self.lower=slash.DeltaAgent(features.LOWER_INPUT_DIM,43,recipe,gates=False)
        self.upper=slash.DeltaAgent(features.UPPER_INPUT_DIM,90,recipe,gates=False)

    def initial_state(self,lower,upper,roots):
        """Two native primer poses B,2,41/90 and roots B,2,12 only."""
        if lower.shape[1]!=2 or upper.shape[1]!=2 or roots.shape[1]!=2:
            raise ValueError('Exactly two primers initialize vanilla inference')
        points=roots[...,:3];axes=roots[...,3:].reshape(-1,2,3,3)
        delta,yaw=features.initial_root_command(roots[:,0],roots[:,1])
        states=[];root_points=[];root_axes=[]
        batch=lower.shape[0];ids=torch.arange(batch,device=lower.device)
        for frame in range(2):
            point,rotation=points[:,frame],axes[:,frame]
            if self.kind=='dodge':
                world,_=native._decode(self.skeleton,lower[:,frame],upper[:,frame],point,rotation,ids)
                chosen,chosen_axes=features.adaptive_com_root(world,self.skeleton.mass_weights,axes[:,0])
                l,u=native._held_target(lower[:,frame],upper[:,frame],self.skeleton,point,rotation,chosen,chosen_axes)
                point,rotation=chosen,chosen_axes
            else:l,u=lower[:,frame],upper[:,frame]
            states.append((l,u));root_points.append(point);root_axes.append(rotation)
        return State(*states[0],*states[1],root_points[0],root_axes[0],root_points[1],root_axes[1],
                     axes[:,0],delta,yaw)

    def forward(self,state,pelvis_current,pelvis_next,collider_current,collider_next,event,
                target_world,attack_type,*,authored_next_root=None):
        if self.kind=='parry' and authored_next_root is None:
            raise ValueError('Parry requires its external authored next root')
        if self.kind=='dodge' and authored_next_root is not None:
            raise ValueError('Dodge cannot consume an authored future root')
        previous_lower,previous_upper=native._held_target(
            state.previous_lower,state.previous_upper,self.skeleton,
            state.previous_root,state.previous_axes,state.current_root,state.current_axes)
        current_lower,current_upper=state.current_lower,state.current_upper
        context=features.conditioning(pelvis_current,pelvis_next,collider_current,collider_next,event,
            state.initial_delta_world,state.initial_delta_yaw,state.current_root,state.current_axes,
            target_world,attack_type)
        lower_output,_=self.lower(features.lower_input(previous_lower,current_lower,context))
        # Exactly one learned lower/pin pass; there is no second frozen lower.
        next_lower,pins=slash.clean_lower_delta(self.skeleton.runtime,self.skeleton.lower_store,
            current_lower,current_lower,lower_output[...,:41],lower_output[...,41:],
            effective_pins=lower_output[...,41:].clamp(0.,1.) if self.pin_command_mode==LINEAR_PIN_MODE else None)
        batch=current_lower.shape[0];ids=torch.arange(batch,device=current_lower.device)
        zero=state.current_root.new_zeros((batch,3))
        identity=torch.eye(3,device=zero.device,dtype=zero.dtype)[None].expand(batch,-1,-1)
        current_base,next_base,lower_positions,lower_rotations=native.paired_base_upper_with_globals(
            self.skeleton,ids,current_lower,next_lower,zero,identity)
        carried=slash.carry_upper_hybrid_deviation(current_upper,current_base,next_base)
        upper_output,_=self.upper(features.upper_input(previous_upper,current_upper,
            previous_lower,current_lower,next_lower,context))
        next_upper=slash.clean_upper_state(carried+upper_output)
        lower_world=lower_positions @ state.current_axes+state.current_root[:,None]
        lower_world_axes=lower_rotations @ state.current_axes[:,None]
        world,world_axes=slash.full_fk_globals(self.skeleton.runtime,ids,next_lower,next_upper,
            state.current_root,state.current_axes,frozen_pos=lower_world,frozen_rot=lower_world_axes)
        # frozen_pos/frozen_rot are legacy names for cached lower FK geometry;
        # they are not neural predictions. Reuse them to avoid duplicate FK.
        row=features.predictor_row(previous_lower,previous_upper,current_lower,current_upper,
                                   next_lower,next_upper,context)
        if self.kind=='dodge':
            next_root,next_axes=features.adaptive_com_root(world,self.skeleton.mass_weights,state.initial_axes)
        else:
            next_root=authored_next_root[...,:3]
            next_axes=authored_next_root[...,3:].reshape(batch,3,3)
        local_lower,local_upper=native._held_target(next_lower,next_upper,self.skeleton,
            state.current_root,state.current_axes,next_root,next_axes)
        following=State(current_lower,current_upper,local_lower,local_upper,state.current_root,
            state.current_axes,next_root,next_axes,state.initial_axes,state.initial_delta_world,state.initial_delta_yaw)
        return Proposal(following,world,world_axes,row,pins,lower_output,upper_output)
