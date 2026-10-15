"""Disposable same-host PPO phase timings; never writes a production model."""
import argparse
import json
import os
from pathlib import Path
import statistics
import time
import zipfile

import train
import torch
import yaml
from neutral_pose import NeutralPoseEnv
from learning.ppo_agent import PPOAgent
from profile_training import run_profiled_update
from resume import restore

p = argparse.ArgumentParser()
p.add_argument('--worlds', type=int, required=True)
p.add_argument('--checkpoint', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
a.output.mkdir(exist_ok=False)
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
os.chdir(train.REPO)
with zipfile.ZipFile(a.checkpoint) as z:
    cfg = yaml.safe_load(z.read('env_config.yaml'))
    engine = yaml.safe_load(z.read('engine_config.yaml'))
    acfg = yaml.safe_load(z.read('agent_config.yaml'))
train.upstream.mp_util.init(0, 1, 'cuda:0', 6742)
args = train.upstream.load_args(['train', '--rand_seed', '20261014'])
train.upstream.set_rand_seed(args)
env = NeutralPoseEnv(cfg, engine, a.worlds, 'cuda:0', False)
agent = PPOAgent(acfg, env, 'cuda:0')
restore(agent, a.checkpoint)
agent._curr_obs, agent._curr_info = agent._reset_envs()
agent._init_train()
times = []
for i in range(14):
    torch.cuda.synchronize()
    start = time.perf_counter()
    result = agent._train_iter()
    torch.cuda.synchronize()
    times.append(time.perf_counter() - start)
    agent._iter += 1
    assert all(bool(torch.isfinite(v).all()) for v in agent.parameters())
for i in range(2):
    run_profiled_update(agent, agent._train_iter, a.output, i)
    agent._iter += 1
report = dict(worlds=a.worlds, seconds=times, median_seconds=statistics.median(times[4:]),
              checkpoint=str(a.checkpoint), production_state_changed=False,
              note='Same saved policy/optimizer/config on same host. Fresh physical episodes; trajectories are not identical between world counts. Profiling adds synchronization; unprofiled timings reported separately.')
(a.output/'summary.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report), flush=True)
