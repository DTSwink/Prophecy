"""Experimental upper-only Parry; accepted locomotion is immutable input.

The cache is lower-only FK, never a future upper proposal. Only the current
completed locomotion delta is observed, alongside the attacker's completed
delta. No authored block time or future defender pose enters the policy.
"""
from dataclasses import fields
import torch
from transition_agents import State, VanillaDefense, native, slash
import transition_features as features
from transition_rollout import Trajectory

CHECKPOINT_KIND='parry_frozen_walk_run_upper_free_contact_v1'
DRAWN_CONTRACT='defender_drawn_policy_tail_bit_v1'
LOWER_NAMES=('pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r')


class FrozenUpperParry(torch.nn.Module):
    def __init__(self,skeleton,cache,recipe=None,defender_drawn=None):
        super().__init__();self.kind='parry';self.skeleton=skeleton
        self.register_buffer('defender_drawn',defender_drawn,persistent=False)
        self.upper=slash.DeltaAgent(features.UPPER_INPUT_DIM+int(defender_drawn is not None),90,recipe or slash.Recipe(),gates=False)
        self.register_buffer('lower_indices',torch.tensor([skeleton.body_names.index(n) for n in LOWER_NAMES],
            device=cache['lower'].device),persistent=False)
        for key in ('lower','roots','positions','rotations','baseline_upper'):
            self.register_buffer('cached_'+key,cache[key].detach(),persistent=False)

    initial_state=VanillaDefense.initial_state

    def step(self,state,episode,frame):
        root=self.cached_roots[:,frame];point=root[:,:3];axes=root[:,3:].reshape(-1,3,3)
        next_lower=self.cached_lower[:,frame];base=self.cached_baseline_upper[:,frame]
        previous_lower,previous_upper=native._held_target(state.previous_lower,state.previous_upper,
            self.skeleton,state.previous_root,state.previous_axes,state.current_root,state.current_axes)
        held_lower,held_base=native._held_target(next_lower,base,self.skeleton,
            point,axes,state.current_root,state.current_axes)
        current_base=self.cached_baseline_upper[:,frame-1]
        context=features.conditioning(episode.pelvis[:,frame-1],episode.pelvis[:,frame],
            episode.collider[:,frame-1],episode.collider[:,frame],episode.event[:,frame],
            state.initial_delta_world,state.initial_delta_yaw,state.current_root,state.current_axes,
            episode.target_world,episode.attack_type)
        policy_input=features.upper_input(previous_upper,state.current_upper,
            previous_lower,state.current_lower,held_lower,context)
        if self.defender_drawn is not None:
            policy_input=torch.cat((policy_input,self.defender_drawn.reshape(-1,1)),dim=-1)
        output,_=self.upper(policy_input)
        carried=slash.carry_upper_hybrid_deviation(state.current_upper,current_base,held_base)
        next_upper=slash.clean_upper_state(carried+output)
        ids=torch.arange(next_lower.shape[0],device=next_lower.device)
        world,world_axes=slash.full_fk_globals(self.skeleton.runtime,ids,held_lower,next_upper,
            state.current_root,state.current_axes,frozen_pos=self.cached_positions[:,frame],
            frozen_rot=self.cached_rotations[:,frame],baseline_upper=held_base)
        # This is the architecture's frozen joint ownership, not a pose repair.
        # Avoid even decoder-roundoff changes to the pelvis and either leg.
        world=world.index_copy(1,self.lower_indices,self.cached_positions[:,frame].index_select(1,self.lower_indices))
        world_axes=world_axes.index_copy(1,self.lower_indices,self.cached_rotations[:,frame].index_select(1,self.lower_indices))
        row=features.predictor_row(previous_lower,previous_upper,state.current_lower,state.current_upper,
            held_lower,next_upper,context)
        _,local_upper=native._held_target(held_lower,next_upper,self.skeleton,
            state.current_root,state.current_axes,point,axes)
        following=State(state.current_lower,state.current_upper,next_lower,local_upper,
            state.current_root,state.current_axes,point,axes,state.initial_axes,
            state.initial_delta_world,state.initial_delta_yaw)
        return following,world,world_axes,row


def rollout(agent,episode):
    state=agent.initial_state(agent.cached_lower[:,:2],episode.upper_primers,agent.cached_roots[:,:2])
    batch=episode.valid.shape[0];ids=torch.arange(batch,device=episode.valid.device)
    points=[];rotations=[];roots=[];lowers=[];uppers=[];rows=[]
    for lower,upper,root,axes in (
        (state.previous_lower,state.previous_upper,state.previous_root,state.previous_axes),
        (state.current_lower,state.current_upper,state.current_root,state.current_axes)):
        p,r=native._decode(agent.skeleton,lower,upper,root,axes,ids)
        frame=len(points)
        p=p.index_copy(1,agent.lower_indices,agent.cached_positions[:,frame].index_select(1,agent.lower_indices))
        r=r.index_copy(1,agent.lower_indices,agent.cached_rotations[:,frame].index_select(1,agent.lower_indices))
        points.append(p);rotations.append(r);roots.append(torch.cat((root,axes.flatten(-2)),-1))
        lowers.append(lower);uppers.append(upper)
    for frame in range(2,episode.valid.shape[1]):
        proposed,p,r,row=agent.step(state,episode,frame);active=episode.valid[:,frame]
        def keep(new,old):return torch.where(active.reshape(batch,*([1]*(new.ndim-1))),new,old)
        state=State(*(keep(getattr(proposed,f.name),getattr(state,f.name)) for f in fields(state)))
        points.append(keep(p,points[-1]));rotations.append(keep(r,rotations[-1]))
        roots.append(torch.cat((state.current_root,state.current_axes.flatten(-2)),-1))
        lowers.append(state.current_lower);uppers.append(state.current_upper);rows.append(row)
    pins=points[0].new_zeros((batch,len(rows),2))
    return Trajectory(*(torch.stack(x,1) for x in (points,rotations,roots,lowers,uppers,rows)),pins,None)
