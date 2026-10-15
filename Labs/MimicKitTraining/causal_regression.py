"""Bounded, disposable regression experiments. Never writes production runs."""
import os
os.environ['PYGLET_HEADLESS'] = 'true'
os.environ['OMP_NUM_THREADS'] = '1'
import argparse, json, time
from pathlib import Path
ROOT = Path('/workspace/mimickit_trial')
import sys
sys.path.insert(0, str(ROOT / 'MimicKit/mimickit'))
import numpy as np
import torch
import yaml
import run as upstream
from recovery_pose import RecoveryPoseEnv
from resume import restore
from health import install_guard
from learning.base_agent import AgentMode
from util import torch_util

p = argparse.ArgumentParser()
p.add_argument('--branch', choices=['stock', 'frozen', 'norm_only', 'frozen_low_lr', 'stock_low_lr'], required=True)
p.add_argument('--seed', type=int, default=9017)
p.add_argument('--updates', type=int, default=300)
p.add_argument('--checkpoint', type=int, default=150)
p.add_argument('--evaluate', type=int)
p.add_argument('--eval-seed', type=int, default=7719)
p.add_argument('--label', default='')
p.add_argument('--trace-first', action='store_true')
p.add_argument('--deadline', type=float, required=True)
a = p.parse_args()
assert time.time() < a.deadline
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
os.chdir(ROOT / 'MimicKit')
source = ROOT / 'runs' / json.loads((ROOT/'sweep.json').read_text())['trials'][1]['name']
assert not a.label or a.label.replace('_','').isalnum()
out = ROOT / 'causal_regression' / (f'cp{a.checkpoint}_{a.branch}_seed{a.seed}' + ('_'+a.label if a.label else ''))
out.mkdir(parents=True, exist_ok=True)
args = upstream.load_args(['train', '--env_config', str(source/'env_config.yaml'),
    '--engine_config', str(source/'engine_config.yaml'), '--agent_config', str(source/'agent_config.yaml'),
    '--rand_seed', str(a.seed), '--visualize', 'false', '--logger', 'tb'])
upstream.mp_util.init(0, 1, 'cuda:0', 6741)
upstream.set_rand_seed(args)
cfg = yaml.safe_load((source/'env_config.yaml').read_text())
cfg['reset_seed'] = a.seed if a.evaluate is None else a.eval_seed
env = RecoveryPoseEnv(cfg, yaml.safe_load((source/'engine_config.yaml').read_text()), 128, 'cuda:0', False)
agent = upstream.build_agent(args, env, 'cuda:0')

if a.evaluate is not None:
    agent.load_state_dict(torch.load(out/f'model_{a.evaluate:04d}.pt', map_location='cuda:0', weights_only=True))
    agent.eval()
    agent.set_mode(AgentMode.TRAIN)
    torch.manual_seed(a.eval_seed)
    torch.cuda.manual_seed_all(a.eval_seed)
    obs, info = env.reset()
    initial = env._engine.get_body_pos(env._get_char_id()).clone()
    back = env._starts_on_back.clone()
    errors, positions, clipping, rotations, roots = [], [], [], [], []
    initial_rotation = env._engine.get_root_rot(env._get_char_id()).clone()
    with torch.no_grad():
        for step in range(45):
            action, _ = agent._decide_action(obs, info)
            clipping.append((action != action.clamp(env._action_bound_low, env._action_bound_high)).float().mean())
            obs, reward, done, info = env.step(action)
            assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
            errors.append(env._pose_mse().clone())
            positions.append(env._engine.get_body_pos(env._get_char_id()).clone())
            rotations.append(env._engine.get_root_rot(env._get_char_id()).clone())
            roots.append(env._engine.get_root_pos(env._get_char_id()).clone())
    err, pos = torch.stack(errors), torch.stack(positions)
    names = env._engine.get_obj_body_names(env._get_char_id())
    rot = torch.cat([initial_rotation[None], torch.stack(rotations)])
    heading = torch_util.calc_heading(rot)
    dh = torch.atan2(torch.sin(heading[1:]-heading[:-1]), torch.cos(heading[1:]-heading[:-1])).abs()
    dq = 2*torch.acos((rot[1:]*rot[:-1]).sum(-1).abs().clamp(0,1))
    # Isolate reward change due only to heading: keep current positions fixed.
    rootpos = torch.stack(roots).clone(); rootpos[:,:,2] = 0
    centered = pos-rootpos[:,:,None,:]
    prev_h = torch_util.calc_heading_quat_inv(rot[:-1])[:,:,None,:].expand(-1,-1,pos.shape[2],-1)
    prev_local = torch_util.quat_rotate(prev_h, centered)
    prev_heading_mse = (prev_local-env._neutral_positions).square().mean((-2,-1))
    flips = (dh > torch.pi/2) & (dq < torch.pi/18)
    report = dict(branch=a.branch, checkpoint=a.checkpoint, updates=a.evaluate, train_seed=a.seed,
        eval_seed=a.eval_seed, mse=float(err.mean()), back=int(back.sum()),
        mse_back=float(err[:,back].mean()), mse_front=float(err[:,~back].mean()),
        head_peak=float(pos[:,:,names.index('head'),2].amax(0).mean()),
        pelvis_peak=float(pos[:,:,0,2].amax(0).mean()), action_clipping=float(torch.stack(clipping).mean()), finite=True,
        heading_flip_with_root_under_10deg_count=int(flips.sum()),
        heading_flip_after_first_frame_count=int(flips[1:].sum()),
        heading_only_mse_change_abs_max=float((err-prev_heading_mse).abs().max()))
    stem=f'eval_{a.evaluate:04d}_{a.eval_seed}'
    (out/(stem+'.json')).write_text(json.dumps(report, indent=2))
    np.savez_compressed(out/(stem+'.npz'), mse=err.cpu().numpy(), initial=initial.cpu().numpy(), back=back.cpu().numpy(),
        heading_delta=dh.cpu().numpy(), root_rotation_delta=dq.cpu().numpy(), heading_only_mse_change=(err-prev_heading_mse).cpu().numpy())
    print('EVALUATION', json.dumps(report), flush=True)
else:
    restore(agent, source/f'checkpoint_{a.checkpoint:07d}.zip')
    agent._init_train()
    # Matched forks intentionally start fresh physical episodes and RNG streams.
    torch.manual_seed(a.seed)
    torch.cuda.manual_seed_all(a.seed)
    np.random.seed(a.seed)
    agent._curr_obs, agent._curr_info = env.reset()
    if a.trace_first:
        torch.save(dict(obs=agent._curr_obs.cpu(), root_rot=env._engine.get_root_rot(env._get_char_id()).cpu(),
            body_pos=env._engine.get_body_pos(env._get_char_id()).cpu(),
            rng=torch.get_rng_state(), cuda_rng=torch.cuda.get_rng_state()),out/'initial_trace.pt')
    if a.branch.startswith('frozen'):
        agent._need_normalizer_update = lambda: False
    if a.branch.endswith('low_lr'):
        for group in agent._actor_optimizer._optimizer.param_groups:
            group['lr'] = 3e-7
    if a.branch == 'norm_only':
        agent._update_model = lambda: {}
    # Measure policy movement on the same states; this does not alter optimization.
    shifts = {}
    update_model = agent._update_model
    update_norm = agent._update_normalizers
    def policy_mean():
        with torch.no_grad():
            obs = agent._exp_buffer.get_data_flat('obs')[:512]
            return agent._model.eval_actor(agent._obs_norm.normalize(obs)).mode.clone()
    def tracked_model():
        if agent._iter % 10: return update_model()
        before = policy_mean()
        if a.trace_first and agent._iter == 0:
            torch.save({**{k:v.cpu() for k,v in agent._exp_buffer._buffers.items()},
                'sample_permutation':agent._exp_buffer._sample_buf.cpu(),
                'before_mean':before.cpu()},out/'rollout_trace.pt')
        result = update_model()
        after = policy_mean()
        shifts['optimizer_kl'] = float(((after-before).square().sum(-1)/(2*.005**2)).mean())
        shifts['after_optimizer'] = after
        shifts['normalizer_kl'] = 0.
        return result
    def tracked_norm():
        result = update_norm()
        if agent._iter % 10 == 0:
            after = policy_mean()
            shifts['normalizer_kl'] = float(((after-shifts['after_optimizer']).square().sum(-1)/(2*.005**2)).mean())
        return result
    agent._update_model = tracked_model
    agent._update_normalizers = tracked_norm
    install_guard(agent, lambda report: (out/'failure.json').write_text(json.dumps(report)))
    torch.save(agent.state_dict(), out/'model_0000.pt')
    start = time.time()
    records = []
    for i in range(a.updates):
        if time.time() >= a.deadline: break
        agent._iter = i
        info = agent._train_iter()
        agent._sample_count = agent._update_sample_count()
        assert all(torch.isfinite(t).all() for t in agent.state_dict().values() if t.is_floating_point())
        record = dict(update=i+1, mse=-float(info['mean_return']),
            clip=float(info.get('clip_frac', 0)), elapsed=time.time()-start,
            episodes=int(info['num_eps']))
        if i % 10 == 0:
            record.update({k:v for k,v in shifts.items() if k.endswith('_kl')})
        records.append(record)
        if (i+1) % 10 == 0:
            (out/'progress.json').write_text(json.dumps(record))
            print('PROGRESS', json.dumps(record), flush=True)
        # Match production's first/output reset cadence, common across variants.
        if i % 50 == 0:
            agent._train_return_tracker.reset()
            agent._curr_obs, agent._curr_info = env.reset()
        if (i+1) % 50 == 0:
            torch.save(agent.state_dict(), out/f'model_{i+1:04d}.pt')
    torch.save(agent.state_dict(), out/f'model_{len(records):04d}.pt')
    (out/'training.json').write_text(json.dumps(dict(arguments=vars(a), records=records), indent=2))
    print('COMPLETE', a.branch, len(records), flush=True)
