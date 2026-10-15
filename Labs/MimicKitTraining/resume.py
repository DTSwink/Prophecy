"""Resume learned state while deliberately starting fresh physical episodes."""
import io
import random
import zipfile
import json
import hashlib
from pathlib import Path
import numpy as np
import torch

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
    agent._actor_optimizer._optimizer.load_state_dict(state['actor_optimizer'])
    agent._critic_optimizer._optimizer.load_state_dict(state['critic_optimizer'])
    agent._actor_optimizer._steps=state['actor_steps']
    agent._critic_optimizer._steps=state['critic_steps']
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
                optimizer_restored=True,normalizer_restored=True,fresh_physical_episodes=True,
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
