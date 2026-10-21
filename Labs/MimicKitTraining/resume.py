"""Resume learned state while deliberately starting fresh physical episodes."""
import io
import random
import zipfile
import json
import hashlib
import math
from pathlib import Path
import numpy as np
import torch

def migrate_physical_observation_scales(agent):
    """Broaden physical scales; preserve the previously unclipped affine map.

    Adam moments transform as gradients under W_new = W_old * new_std / old_std.
    Saved tensors make subsequent resumes idempotent; command scales stay fixed.
    """
    norm = agent._obs_norm
    if norm._std.shape != (154,):
        raise ValueError('Physical-scale migration requires the audited 154-input layout')
    old = norm._std.detach().clone()
    floor = torch.zeros_like(old)
    floor[0] = .25                 # pelvis world height, metres
    floor[1:7] = .25               # root orientation tan/normal
    floor[7:10] = 1.               # root linear velocity, m/s
    floor[10:13] = 2.              # root angular velocity, rad/s
    floor[13:97] = .25             # 14 joint orientation tan/normal pairs
    floor[97:131] = 2.             # 34 local DOF velocities, rad/s
    floor[131:146] = .25           # 5 key-body positions relative to pelvis, m
    new = torch.maximum(old, floor)
    ratio = new / old
    changed = new > old
    with torch.no_grad():
        for name in ('actor', 'critic'):
            layer = getattr(agent._model, '_'+name+'_layers')[0]
            layer.weight.mul_(ratio[None])
            optimizer = getattr(agent, '_'+name+'_optimizer')._optimizer
            state = optimizer.state.get(layer.weight, {})
            if 'exp_avg' in state:
                state['exp_avg'].div_(ratio[None])
                state['exp_avg_sq'].div_(ratio[None].square())
                if 'max_exp_avg_sq' in state:
                    state['max_exp_avg_sq'].div_(ratio[None].square())
            elif 'momentum_buffer' in state:
                state['momentum_buffer'].div_(ratio[None])
        norm._std.copy_(new)
        dtype = norm._mean_sq.dtype if norm._mean_sq is not None else norm._mean.dtype
        norm._mean_sq = norm._mean.to(dtype).square()+new.to(dtype).square()
    return dict(version='physical_scales_v1', changed_channels=int(changed.sum()),
        old_std=old.cpu().tolist(), new_std=new.cpu().tolist(),
        mean_unchanged=True, commands_unchanged=True, first_layers_compensated=True,
        optimizer_moments='First-layer gradient moments divided by scale ratio; counters/LR and other parameters unchanged',
        limitation='Previously clipped states change; affine responses preserved where old inputs were unclipped')


def override_actor_learning_rate(agent, value):
    """Explicit resume override: retain Adam moments, counters and all weights."""
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Actor learning rate must be finite and positive')
    groups = agent._actor_optimizer._optimizer.param_groups
    previous = [float(group['lr']) for group in groups]
    for group in groups:
        group['lr'] = value
    return dict(previous=previous, requested=value, optimizer_state_preserved=True)

def override_fixed_action_noise(agent, value):
    """Apply explicit exploration change after checkpoint tensors are restored."""
    value=float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Action noise must be finite and positive')
    logstd=agent._model._action_dist._logstd_net
    previous=logstd.detach().exp().cpu().tolist()
    with torch.no_grad():logstd.fill_(math.log(value))
    return dict(previous=previous,requested=value,actual=logstd.detach().exp().cpu().tolist())

def append_height_records(model, state):
    """142 -> 144 inputs, preserving every old activation and momentum column.

    The new height records start with unit normalization and zero input weights.
    Existing peak-sum/time inputs retain their positions and meaning.
    """
    for part in ['actor', 'critic']:
        key=f'_model._{part}_layers.0.weight'
        weight=model[key]
        assert weight.shape == (1024, 142)
        model[key]=torch.cat((weight, weight.new_zeros((1024, 2))), dim=1)
        optimizer=state[f'{part}_optimizer']
        first=optimizer['param_groups'][0]['params'][0]
        momentum=optimizer['state'][first]['momentum_buffer']
        assert momentum.shape == weight.shape
        optimizer['state'][first]['momentum_buffer']=torch.cat((momentum, momentum.new_zeros((1024, 2))), dim=1)
    for key, fill in [('_mean', 0), ('_std', 1)]:
        value=model['_obs_norm.'+key]
        assert value.shape == (142,)
        model['_obs_norm.'+key]=torch.cat((value, value.new_full((2,), fill)))
    for key, fill in [('_mean_sq', 1), ('_new_sum', 0), ('_new_sum_sq', 0)]:
        value=state['normalizer_aux']['_obs_norm'][key]
        if value is not None:
            assert value.shape == (142,)
            state['normalizer_aux']['_obs_norm'][key]=torch.cat((value, value.new_full((2,), fill)))

def restore(agent,archive,add_height_records=False):
    with zipfile.ZipFile(archive) as z:
        model=torch.load(io.BytesIO(z.read('model.pt')),map_location=agent._device,weights_only=True)
        # Only our own checksum-verified checkpoint bundles are accepted by deployment.
        state=torch.load(io.BytesIO(z.read('resume_state.pt')),map_location='cpu',weights_only=False)
    if add_height_records:
        append_height_records(model,state)
    agent.load_state_dict(model)
    adaptive = getattr(agent._env, '_adaptive_rows', None)
    if adaptive is not None and 'adaptive_rows' in state:
        adaptive.restore(state['adaptive_rows'], agent._env._fixed_motion_ids)
    restored = {}
    for part in ('actor', 'critic'):
        wrapper = getattr(agent, '_'+part+'_optimizer')
        current = wrapper._optimizer.param_groups[0]
        saved = state[part+'_optimizer']['param_groups'][0]
        same_kind = ('betas' in current) == ('betas' in saved)
        if same_kind:
            wrapper._optimizer.load_state_dict(state[part+'_optimizer'])
            wrapper._steps = state[part+'_steps']
        else:
            # Explicit SGD -> Adam migration: retain learned weights/counters,
            # initialize fresh moments rather than loading incompatible state.
            wrapper._steps = 0
        restored[part] = same_kind
    if hasattr(agent,'_disc_optimizer'):
        agent._disc_optimizer._optimizer.load_state_dict(state['disc_optimizer'])
        agent._disc_optimizer._steps=state['disc_steps']
    modules=dict(agent.named_modules())
    for name,values in state['normalizer_aux'].items():
        for key,value in values.items():
            setattr(modules[name],key,value.to(agent._device) if torch.is_tensor(value) else value)
    original_init=agent._init_train
    original_count=agent._update_sample_count
    prior_samples=int(state['samples'])
    def initialize():
        original_init()
        agent._sample_count=prior_samples
        torch.set_rng_state(state['torch_rng'])
        if torch.cuda.is_available():torch.cuda.set_rng_state_all(state['cuda_rng'])
        np.random.set_state(state['numpy_rng']);random.setstate(state['python_rng'])
    agent._init_train=initialize
    agent._update_sample_count=lambda:prior_samples+original_count()
    # Keep upstream's per-run iteration zero and first evaluation. Its loop's
    # test_info is initialized at that first output; global numbering is metadata.
    return dict(prior_samples=prior_samples,iteration_offset=int(state['completed_iteration'])+1,
                optimizer_restored=all(restored.values()),optimizer_restored_by_part=restored,
                normalizer_restored=True,fresh_physical_episodes=True,
                discriminator_optimizer_restored=hasattr(agent,'_disc_optimizer'),
                discriminator_replay_buffer_fresh=hasattr(agent,'_disc_optimizer'),
                appended_zero_weight_height_inputs=2 if add_height_records else 0)

if __name__=='__main__':
    import boto3
    root=Path('/workspace/mimickit_trial')
    control=json.loads((root/'private.json').read_text());receipt=control['resume_checkpoint']
    client=boto3.client('s3',**control['s3'])
    destination=root/'resume.zip'
    client.download_file('aj7d2jzwuq',receipt['key'],str(destination))
    assert hashlib.sha256(destination.read_bytes()).hexdigest()==receipt['sha256'],'Resume checksum mismatch'
    print('Verified resume bundle:',receipt['key'],flush=True)
