"""Self-contained live-lower/upper policy checkpoint and exact inference load.

Frozen weights are stored once in model; only their runtime metadata is kept
separately. No dataset, AE, old checkpoint path, or preview manifest is read
by load_policy. The caller supplies its normal skeleton, locomotion category,
and the current attack family. State (including banks) is owned by the caller.
"""
import copy
from dataclasses import asdict
import torch
from dodge_banked_agent import BankedDodge,CHECKPOINT_KIND,INPUT_DIM,slash
from dodge_movement_banks import CONTRACT,BANK_NAMES,ACTION_DIM,limits_for_families
from dodge_leg_feedback import LEG_CONTRACT,FOOT_FLOOR_CONTRACT

ROOT_CONTRACT='initial_command_extrapolated_persistent_shift_and_yaw_path_v2'
BANK_INPUT_CONTRACT='one_remaining_absolute_m_or_rad_per_bank_v1'


def policy_checkpoint(agent,bank_overrides=None):
    return dict(kind=CHECKPOINT_KIND,model=agent.state_dict(),recipe=asdict(agent.recipe),
        input_dim=INPUT_DIM,output_dim=90+ACTION_DIM,bank_contract=CONTRACT,leg_contract=LEG_CONTRACT,
        bank_names=BANK_NAMES,bank_input_contract=BANK_INPUT_CONTRACT,bank_overrides=copy.deepcopy(bank_overrides or {}),
        lower_identities=dict(agent.frozen.identities),
        lower_runtime={k:{field:copy.deepcopy(cp.get(field,{})) for field in ('config','metadata')}
            for k,cp in agent.frozen.checkpoints.items()},
        prior_type='dodge_regular',prior_scored_channels='upper90',
        foot_floor_contract=FOOT_FLOOR_CONTRACT if agent.foot_floor else None,
        root_contract=ROOT_CONTRACT)


def load_policy(checkpoint,skeleton,categories,attack_families,device='cpu'):
    floor_contract=checkpoint.get('foot_floor_contract')
    if floor_contract not in (None,FOOT_FLOOR_CONTRACT):raise ValueError('Unknown foot-floor inference contract')
    if (checkpoint.get('kind')!=CHECKPOINT_KIND or checkpoint.get('bank_contract')!=CONTRACT or
            checkpoint.get('leg_contract')!=LEG_CONTRACT or
            checkpoint.get('root_contract')!=ROOT_CONTRACT or
            checkpoint.get('bank_input_contract')!=BANK_INPUT_CONTRACT or
            checkpoint.get('input_dim')!=INPUT_DIM or checkpoint.get('output_dim')!=90+ACTION_DIM or
            checkpoint.get('prior_type')!='dodge_regular' or checkpoint.get('prior_scored_channels')!='upper90' or
            tuple(checkpoint.get('bank_names',()))!=BANK_NAMES):
        raise ValueError('Incompatible banked-Dodge inference contract')
    if len(categories)!=len(attack_families) or any(c not in ('walk','run') for c in categories):
        raise ValueError('One accepted walk/run category and attack family required per row')
    runtime={}
    for kind in ('walk','run'):
        prefix='frozen.models.'+kind+'.'
        state={k[len(prefix):]:v for k,v in checkpoint['model'].items() if k.startswith(prefix)}
        if not state:raise ValueError('Frozen '+kind+' weights missing')
        runtime[kind]={**checkpoint['lower_runtime'][kind],'model':state}
    category=torch.tensor([c=='run' for c in categories],device=device,dtype=torch.long)
    limits=limits_for_families(attack_families,checkpoint['bank_overrides'],device=device)
    agent=BankedDodge(skeleton,category,limits,slash.Recipe(**checkpoint['recipe']),runtime,checkpoint['lower_identities'],
        foot_floor=floor_contract==FOOT_FLOOR_CONTRACT)
    agent.load_state_dict(checkpoint['model'],strict=True)
    return agent.eval()
