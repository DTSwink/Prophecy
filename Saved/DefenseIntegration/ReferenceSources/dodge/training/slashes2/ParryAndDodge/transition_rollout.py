"""Pure-policy rollout for the independent vanilla defense controllers.

Only two defender primer poses enter inference. Subsequent dataset poses are
not stored in Episode; labels/block times belong to the objective, not policy.
Parry's external root trajectory is applied after inference, never as features.
"""
from dataclasses import dataclass, fields
import torch
from transition_agents import VanillaDefense, native


@dataclass
class Episode:
    lower_primers: torch.Tensor
    upper_primers: torch.Tensor
    root_primers: torch.Tensor
    pelvis: torch.Tensor
    collider: torch.Tensor
    collider_axes: torch.Tensor
    attack_half: torch.Tensor
    event: torch.Tensor
    target_world: torch.Tensor
    attack_type: torch.Tensor
    times: torch.Tensor
    valid: torch.Tensor
    authored_roots: torch.Tensor | None


@dataclass
class Trajectory:
    positions: torch.Tensor
    rotations: torch.Tensor
    roots: torch.Tensor
    lower: torch.Tensor
    upper: torch.Tensor
    predictor_rows: torch.Tensor
    pin_probabilities: torch.Tensor
    pin_commands: torch.Tensor | None = None
    movement_banks: torch.Tensor | None = None
    root_shifts_world: torch.Tensor | None = None
    root_yaw_offsets: torch.Tensor | None = None
    bank_requests: torch.Tensor | None = None


def prepare(cases, skeleton, kind, device):
    """One-time CPU validation/upload, outside graph capture; no pin labels."""
    if kind not in ('dodge', 'parry') or not cases:
        raise ValueError('Choose one nonempty independent training')
    lengths=[len(case.data['time']) for case in cases]
    if min(lengths)<3:raise ValueError('Two primers plus a controlled frame required')
    maximum=max(lengths)
    def tensor(value):return torch.as_tensor(value,device=device,dtype=torch.float32)
    def pad(value):
        return torch.cat((value,value[-1:].expand(maximum-len(value),*value.shape[1:])))
    rows=[]
    for index,case in enumerate(cases):
        data=case.data
        if (int(data['motion_kind'])<16)!=(kind=='dodge'):
            raise ValueError('Dodge and Parry cannot share one controller training')
        roots=tensor(data['root']);axes=roots[:,3:].reshape(-1,3,3)
        times=tensor(data['time'])
        if not bool((times[1:]>times[:-1]).all()):raise ValueError('Non-increasing motion times')
        # Never project/read a future defender pose for policy initialization.
        lower,upper=native.body_to_agent_states({'body':data['body'][:2]},skeleton,device,index)
        def world(key):
            value=tensor(data[key])
            point=(value[:,:3,None].transpose(-1,-2) @ axes).squeeze(-2)+roots[:,:3]
            rotation=(value[:,3:].reshape(-1,2,3) @ axes).flatten(-2)
            return torch.cat((point,rotation),-1)
        pelvis,collider=world('attacker_pelvis'),world('attack')
        collider_axes=native.tl.rotation_6d_to_matrix(collider[:,3:])
        # Attacker speaks first: its event at the end of this very interval.
        threshold=float(data['hit_time']) if kind=='dodge' else 2.0
        event=(times>=threshold).to(torch.float32)[:,None]
        rows.append((lower,upper,roots[:2],pad(pelvis),pad(collider),pad(collider_axes),
                     tensor(data['attack_half']),pad(event),tensor(data['target_world']),
                     tensor(data['attack_type']),pad(times),pad(roots)))
    stacked=[torch.stack([row[i] for row in rows]) for i in range(12)]
    valid=torch.arange(maximum,device=device)[None]<torch.tensor(lengths,device=device)[:,None]
    return Episode(*stacked[:11],valid,stacked[11] if kind=='parry' else None)


def rollout(agent: VanillaDefense, episode: Episode):
    state=agent.initial_state(episode.lower_primers,episode.upper_primers,episode.root_primers)
    batch=episode.valid.shape[0];ids=torch.arange(batch,device=episode.valid.device)
    points=[];rotations=[];roots=[];lowers=[];uppers=[];rows=[];pins=[];commands=[]
    banked=hasattr(state,'remaining')
    banks=[state.remaining,state.remaining] if banked else None
    shifts=[state.root_shift_world,state.root_shift_world] if banked else None
    yaw_offsets=[state.root_yaw_offset,state.root_yaw_offset] if banked else None
    requests=[] if banked else None
    for lower,upper,root,axes in (
        (state.previous_lower,state.previous_upper,state.previous_root,state.previous_axes),
        (state.current_lower,state.current_upper,state.current_root,state.current_axes)):
        p,r=native._decode(agent.skeleton,lower,upper,root,axes,ids)
        points.append(p);rotations.append(r);roots.append(torch.cat((root,axes.flatten(-2)),-1))
        lowers.append(lower);uppers.append(upper)
    for frame in range(2,episode.valid.shape[1]):
        external=None if episode.authored_roots is None else episode.authored_roots[:,frame]
        proposal=agent(state,episode.pelvis[:,frame-1],episode.pelvis[:,frame],
            episode.collider[:,frame-1],episode.collider[:,frame],episode.event[:,frame],
            episode.target_world,episode.attack_type,authored_next_root=external)
        # A short row has ended even while longer rows still run. Keep EVERY
        # history/root/command tensor and the visible pose at its terminal
        # value; no padded inference is allowed to advance its state.
        active=episode.valid[:,frame]
        def keep(new,old):
            return torch.where(active.reshape(batch,*([1]*(new.ndim-1))),new,old)
        state=type(state)(*(keep(getattr(proposal.state,f.name),getattr(state,f.name))
                            for f in fields(state)))
        if banked:
            banks.append(state.remaining);shifts.append(state.root_shift_world)
            yaw_offsets.append(state.root_yaw_offset)
            requests.append(torch.where(active[:,None],proposal.bank_requests,0.))
        points.append(keep(proposal.positions,points[-1]));rotations.append(keep(proposal.rotations,rotations[-1]))
        roots.append(torch.cat((state.current_root,state.current_axes.flatten(-2)),-1))
        lowers.append(state.current_lower);uppers.append(state.current_upper)
        rows.append(proposal.predictor_row);pins.append(proposal.pin_probabilities)
        commands.append(proposal.lower_output[...,41:])
    return Trajectory(*(torch.stack(items,1) for items in
        (points,rotations,roots,lowers,uppers,rows,pins,commands)),
        movement_banks=torch.stack(banks,1) if banked else None,
        root_shifts_world=torch.stack(shifts,1) if banked else None,
        root_yaw_offsets=torch.stack(yaw_offsets,1) if banked else None,
        bank_requests=torch.stack(requests,1) if banked else None)
