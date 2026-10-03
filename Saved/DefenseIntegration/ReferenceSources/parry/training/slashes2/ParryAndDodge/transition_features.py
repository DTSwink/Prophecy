"""Versioned causal contract shared by defense joint priors and vanilla agents.

All three states in a transition use ONE held current-root frame. Joint scoring
uses the actual proposed state change (after native cleaning/pins), not a frozen
proposal or the upper policy's intermediate pelvis-carried residual.
"""
import torch

SCHEMA = 'defense_joint_transition_world_target_v2'
TARGET_CONTRACT = 'fixed_world_point_in_current_root_v2'
LOWER_DIM, UPPER_DIM, MOTION_DIM = 41, 90, 131
CONDITION_FIELDS = (('attacker_pelvis_current',9),('attacker_pelvis_next',9),
    ('attacker_collider_current',9),('attacker_collider_next',9),
    ('event',1),('initial_root_translation',3),('initial_root_yaw',1),
    ('target_in_current_root',3),('attack_type',6))
CONDITION_DIM = sum(width for _,width in CONDITION_FIELDS)
FEATURE_DIM = 3*MOTION_DIM + CONDITION_DIM
LOWER_INPUT_DIM = 2*LOWER_DIM + CONDITION_DIM
UPPER_INPUT_DIM = 2*UPPER_DIM + 3*9 + CONDITION_DIM


def join(fields, widths):
    if len(fields)!=len(widths) or any(value.shape[-1]!=width for value,width in zip(fields,widths)):
        raise ValueError('Defense transition feature width mismatch')
    return torch.cat(fields,dim=-1)


def predictor_row(previous_lower,previous_upper,current_lower,current_upper,
                  next_lower,next_upper,conditioning):
    previous=join((previous_lower,previous_upper),(LOWER_DIM,UPPER_DIM))
    current=join((current_lower,current_upper),(LOWER_DIM,UPPER_DIM))
    proposed=join((next_lower,next_upper),(LOWER_DIM,UPPER_DIM))
    # Proposed pelvis belongs only to the scored delta, NOT its conditioning.
    return join((proposed-current,previous,current,conditioning),
                (MOTION_DIM,MOTION_DIM,MOTION_DIM,CONDITION_DIM))


def lower_input(previous,current,conditioning):
    return join((previous,current,conditioning),(LOWER_DIM,LOWER_DIM,CONDITION_DIM))


def upper_input(previous,current,previous_lower,current_lower,next_lower,conditioning):
    return join((previous,current,previous_lower[...,:9],current_lower[...,:9],
                 next_lower[...,:9],conditioning),(UPPER_DIM,UPPER_DIM,9,9,9,CONDITION_DIM))


def initial_root_command(root0,root1):
    """Persistent world translation and wrapped yaw delta, initialized ONCE.

    Native roots have their third row pointing up, and -row1 pointing forward.
    Values are displacement per authored 30-Hz frame, not velocity per second.
    """
    rotation0=root0[...,3:].reshape(*root0.shape[:-1],3,3)
    rotation1=root1[...,3:].reshape(*root1.shape[:-1],3,3)
    yaw0=torch.atan2(-rotation0[...,1,0],-rotation0[...,1,2])
    yaw1=torch.atan2(-rotation1[...,1,0],-rotation1[...,1,2])
    change=yaw1-yaw0
    return root1[...,:3]-root0[...,:3],torch.atan2(torch.sin(change),torch.cos(change))[...,None]


def root_command_in_current(delta_world,delta_yaw,current_root_axes):
    translation=(delta_world.unsqueeze(-2) @ current_root_axes.transpose(-1,-2)).squeeze(-2)
    return torch.cat((translation,delta_yaw),-1)


def world_transform_in_root(value,root_position,root_axes):
    """World position3+row-axis rotation6 -> current-root representation."""
    inverse=root_axes.transpose(-1,-2)
    point=((value[...,:3]-root_position).unsqueeze(-2) @ inverse).squeeze(-2)
    rot=(value[...,3:].reshape(*value.shape[:-1],2,3) @ inverse).flatten(-2)
    return torch.cat((point,rot),-1)


def world_point_in_root(point_world,root_position,root_axes):
    """Exact row-basis inverse, including native signed/nonorthogonal axes.

    Analytic 3x3 inverse avoids linalg synchronization and works in CUDA graphs.
    Do not assume native stored matrices are perfectly orthonormal.
    """
    a,b,c=root_axes.unbind(-2)
    bc=torch.linalg.cross(b,c);ca=torch.linalg.cross(c,a);ab=torch.linalg.cross(a,b)
    inverse=torch.stack((bc,ca,ab),-1)/(a*bc).sum(-1)[...,None,None]
    return ((point_world-root_position).unsqueeze(-2) @ inverse).squeeze(-2)


def conditioning(pelvis_current,pelvis_next,collider_current,collider_next,event,
                 initial_delta_world,initial_delta_yaw,root_position,root_axes,
                 target_world,attack_type):
    """Only attacker current/end states and initial root command are accepted.

    There is deliberately no trajectory, label, block timestamp, future root,
    cumulative shift, or frozen state argument. Spear pelvis remains exactly 0
    even after rebasing a translated/rotated root.
    """
    spear=attack_type[...,-1:]>=.5
    def pelvis(value):
        local=world_transform_in_root(value,root_position,root_axes)
        return torch.where(spear,torch.zeros_like(local),local)
    return join((pelvis(pelvis_current),pelvis(pelvis_next),
        world_transform_in_root(collider_current,root_position,root_axes),
        world_transform_in_root(collider_next,root_position,root_axes),event,
        root_command_in_current(initial_delta_world,initial_delta_yaw,root_axes),
        world_point_in_root(target_world,root_position,root_axes),attack_type),(9,9,9,9,1,4,3,6))


def adaptive_com_root(world_body,mass_weights,initial_axes):
    """Zero tolerance; only the root moves here. No authored trajectory input."""
    com=(world_body*mass_weights[...,None]).sum(-2)
    root=torch.stack((com[...,0],torch.zeros_like(com[...,1]),com[...,2]),-1)
    return root,initial_axes


def freeze_prior(prior):
    prior.eval()
    for parameter in prior.parameters():parameter.requires_grad_(False)
    return prior


def prior_score(prior,row,mean,std):
    """Same condition-only learned predictor as Slash; score only delta131.

    Do not detach the current/history conditioning: controller gradients through
    the fixed prior remain available, as in existing Slash prior scoring.
    """
    normalized=(row-mean)/std
    expected=prior(normalized)
    return (normalized[...,:MOTION_DIM]-expected[...,:MOTION_DIM]).square().mean(-1)
