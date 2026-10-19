"""Disposable local PPO update audit; same rollout/momentum for each learning rate."""
import os, sys, io, json, gzip, zipfile, copy, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'Saved/MimicKitMotorAudit/source'
OUT=ROOT/'Saved/MimicKitEquipment/torque-regression'
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(Path(__file__).parent),str(SOURCE/'MimicKit/mimickit')]
os.environ['PYGLET_HEADLESS']='true';os.environ['OMP_NUM_THREADS']='1'
import torch, warp as wp, yaml
from omni_walk import OmniWalkEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(711)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6797)
    os.chdir(SOURCE/'MimicKit')
    with zipfile.ZipFile(OUT/'models.zip') as z:
        cfg={n:yaml.safe_load(z.read('16562/'+n+'_config.yaml').decode().replace('/workspace/mimickit_trial',SOURCE.as_posix())) for n in ['env','engine','agent']}
        model=torch.load(io.BytesIO(z.read('16562/model.pt')),map_location='cuda:0',weights_only=True)
    state=torch.load(io.BytesIO(gzip.decompress((OUT/'state16562.gz').read_bytes())),map_location='cpu',weights_only=False)
    cfg['env']['motion_file']=str(OUT/'motions.yaml');cfg['env'].pop('adaptive_motion_rows',None)
    begun=time.perf_counter();env=OmniWalkEnv(cfg['env'],cfg['engine'],512,'cuda:0',False)
    env._fixed_motion_ids.copy_(state['adaptive_rows']['assignments'].to('cuda:0'))
    agent=OmniPPOAgent(cfg['agent'],env,'cuda:0');agent.load_state_dict(model)
    agent._actor_optimizer._optimizer.load_state_dict(state['actor_optimizer'])
    agent._critic_optimizer._optimizer.load_state_dict(state['critic_optimizer'])
    agent._init_train();agent._sample_count=state['samples'];agent.eval();agent.set_mode(AgentMode.TRAIN)
    torch.manual_seed(711);agent._curr_obs,agent._curr_info=agent._reset_envs()
    with torch.no_grad():agent._rollout_train(32)
    data_info=agent._build_train_data()
    # Preserve normal PPO ordering: critic sampling advances the minibatch sampler first.
    agent._update_critic(1024,32)
    indices=[agent._exp_buffer._sample_rand_idx(2048).clone() for _ in range(40)]
    flat=agent._exp_buffer._flat_buffers
    probe=flat['obs'][::8]
    with torch.no_grad():
        original=agent._model.eval_actor(agent._obs_norm.normalize(probe)).mode.clone()
    params=list(agent._model.get_actor_params());reports=[]
    for lr in [1e-4,3e-5]:
        agent.load_state_dict(model)
        agent._actor_optimizer._optimizer.load_state_dict(copy.deepcopy(state['actor_optimizer']))
        for group in agent._actor_optimizer._optimizer.param_groups:group['lr']=lr
        updates=[]
        for step,ids in enumerate(indices,1):
            batch={k:v[ids] for k,v in flat.items()}
            info=agent._compute_actor_loss(batch)
            agent._actor_optimizer.step(info['actor_loss'])
            with torch.no_grad():
                dist=agent._model.eval_actor(agent._obs_norm.normalize(probe))
                shift=dist.mode-original
                kl=.5*(shift/.05).square().sum(-1)
                grad=torch.stack([p.grad.square().sum() for p in params if p.grad is not None]).sum().sqrt()
                updates.append(dict(step=step,actor_loss=float(info['actor_loss']),clip_fraction=float(info['clip_frac']),
                    gradient_norm=float(grad),mean_kl=float(kl.mean()),p95_kl=float(kl.quantile(.95)),
                    physical_action_rms_rad_s=float((shift*agent._a_norm._std).square().mean().sqrt())))
        reports.append(dict(lr=lr,updates=updates))
        print('UPDATE',lr,updates[-1],flush=True)
    result=dict(checkpoint=16562,worlds=512,rollout_steps=32,actor_steps=40,noise_std=.05,
                same_rollout=True,same_minibatches=True,same_initial_optimizer_momentum=True,
                allocation='saved peak checkpoint',normalizer_frozen=True,physics_unchanged=True,
                purpose='Prospective one-update stability test, not replay of the historical collapse',
                data_info={k:float(v) for k,v in data_info.items()},reports=reports,elapsed_seconds=time.perf_counter()-begun)
    (OUT/'ppo-update.json').write_text(json.dumps(result,indent=2))
    print('DONE',result['elapsed_seconds'],flush=True)

if __name__=='__main__':main()
