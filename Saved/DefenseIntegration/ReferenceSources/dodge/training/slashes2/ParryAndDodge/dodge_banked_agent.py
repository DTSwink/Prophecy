"""Upper policy plus budgeted lower perturbations, over a LIVE frozen network.

State owns every recurrent quantity, including movement banks and root shift.
The inference signature cannot consume future defender poses/roots/labels.
"""
from dataclasses import dataclass, fields
import torch
from transition_agents import State,Proposal,VanillaDefense,native,slash
import transition_features as features
from dodge_live_lower import LiveLower
from dodge_movement_banks import ACTION_DIM,DEFAULT_LIMITS,GATE_INDICES,controls,next_root,horizontal_world,root_command_delta
from dodge_movement_banks import normalized_bank_cost_requests
from dodge_leg_feedback import solve,configure_hinge_fk

CHECKPOINT_KIND='dodge_live_frozen_lower_banked_upper_v2'
BANK_INPUT_START=features.UPPER_INPUT_DIM+3*(41-9)
BANK_INPUT_SLICE=slice(BANK_INPUT_START,BANK_INPUT_START+len(DEFAULT_LIMITS))
INPUT_DIM=BANK_INPUT_START+len(DEFAULT_LIMITS)+3


@dataclass
class BankState(State):
    remaining: torch.Tensor
    root_shift_world: torch.Tensor
    root_yaw_offset: torch.Tensor


class BankedDodge(torch.nn.Module):
    def __init__(self,skeleton,category,limits,recipe=None,checkpoints=None,identities=None,*,foot_floor=True):
        super().__init__();self.kind='dodge';self.skeleton=skeleton
        self.foot_floor=bool(foot_floor)
        configure_hinge_fk(skeleton)
        self.register_buffer('category',category.long().clone(),persistent=False)
        self.register_buffer('limits',limits.clone(),persistent=False)
        self.frozen=LiveLower(skeleton,limits.device,checkpoints,identities)
        self.recipe=recipe or slash.Recipe()
        self.upper=slash.DeltaAgent(INPUT_DIM,90+ACTION_DIM,self.recipe,gates=False)
        # Actions initially zero; positive gates give movement channels a gradient.
        with torch.no_grad():
            for i in GATE_INDICES:self.upper.delta_head.bias[90+i]=1.
        self.upper.to(limits.device)

    def initial_state(self,lower,upper,roots):
        # Reuse exact two-primer bookkeeping without the old COM root updater.
        # New root is the user's explicit extrapolated command + persistent shift.
        points=roots[...,:3];axes=roots[...,3:].reshape(-1,2,3,3)
        delta,yaw=features.initial_root_command(roots[:,0],roots[:,1])
        return BankState(lower[:,0],upper[:,0],lower[:,1],upper[:,1],points[:,0],axes[:,0],
            points[:,1],axes[:,1],axes[:,0],delta,yaw,self.limits.clone(),torch.zeros_like(delta),torch.zeros_like(yaw))

    def forward(self,state,pelvis_current,pelvis_next,collider_current,collider_next,event,
                target_world,attack_type,*,authored_next_root=None):
        if authored_next_root is not None:raise ValueError('Future authored root is forbidden')
        frozen,pins=self.frozen(state,self.category)
        prev_l,prev_u=native._held_target(state.previous_lower,state.previous_upper,self.skeleton,
            state.previous_root,state.previous_axes,state.current_root,state.current_axes)
        context=features.conditioning(pelvis_current,pelvis_next,collider_current,collider_next,event,
            root_command_delta(state.initial_delta_world,state.root_yaw_offset),state.initial_delta_yaw,
            state.current_root,state.current_axes,target_world,attack_type)
        shift_local=(state.root_shift_world[:,None]@state.current_axes.transpose(-1,-2)).squeeze(1)
        inp=torch.cat((features.upper_input(prev_u,state.current_upper,prev_l,state.current_lower,frozen,context),
            prev_l[:,9:],state.current_lower[:,9:],frozen[:,9:],state.remaining,shift_local),-1)
        output,_=self.upper(inp)
        pelvis_world=(frozen[:,:3,None].transpose(-1,-2)@state.current_axes).squeeze(1)+state.current_root
        action=controls(output[:,90:],state.remaining,pelvis_world[:,1:2])
        modified,applied=solve(self.skeleton,frozen,action,state.current_root,state.current_axes,foot_floor=self.foot_floor)
        # Commands are never rejected/refunded by leg geometry. The solver
        # projects unreachable endpoints to fixed-length reach. Banks charge
        # the requested command path, as before projection, without a dead zone.
        remaining=action.remaining
        ids=torch.arange(len(frozen),device=frozen.device)
        zero=torch.zeros_like(state.current_root)
        identity=torch.eye(3,device=frozen.device,dtype=frozen.dtype)[None].expand(len(frozen),-1,-1)
        current_base,next_base,points,rotations=native.paired_base_upper_with_globals(
            self.skeleton,ids,state.current_lower,modified,zero,identity)
        carried=slash.carry_upper_hybrid_deviation(state.current_upper,current_base,next_base)
        upper=slash.clean_upper_state(carried+output[:,:90])
        points=points@state.current_axes+state.current_root[:,None]
        rotations=rotations@state.current_axes[:,None]
        world,world_axes=slash.full_fk_globals(self.skeleton.runtime,ids,modified,upper,
            state.current_root,state.current_axes,frozen_pos=points,frozen_rot=rotations)
        row=features.predictor_row(prev_l,prev_u,state.current_lower,state.current_upper,modified,upper,context)
        point,axes=next_root(state.current_root,state.current_axes,state.initial_delta_world,
            state.initial_delta_yaw,action.root_horizontal,action.root_yaw,state.root_yaw_offset)
        lower,following_upper=native._held_target(modified,upper,self.skeleton,
            state.current_root,state.current_axes,point,axes)
        shift=state.root_shift_world+horizontal_world(action.root_horizontal,state.current_axes)
        following=BankState(state.current_lower,state.current_upper,lower,following_upper,
            state.current_root,state.current_axes,point,axes,state.initial_axes,state.initial_delta_world,
            state.initial_delta_yaw,remaining,shift,state.root_yaw_offset+action.root_yaw)
        # No learned pin head; recorded pin probabilities are the frozen policy's.
        requests=normalized_bank_cost_requests(action,self.limits)
        return Proposal(following,world,world_axes,row,pins,torch.cat((modified,pins),-1),output[:,:90],requests)
