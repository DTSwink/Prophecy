"""Same-checkpoint, unchanged-training-work benchmark; never deploys its weights."""
import argparse
import hashlib
import json
import os
import random
import signal
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path('/workspace/mimickit_trial')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--protect-main')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    plan = json.loads(Path(args.plan).read_text())
    assert hashlib.sha256(Path(args.checkpoint).read_bytes()).hexdigest() == plan['checkpoint']['sha256']
    assert hashlib.sha256((ROOT/'source.zip').read_bytes()).hexdigest() == plan['source']['sha256']
    sys.path[:0] = [str(ROOT/'pipeline'), str(ROOT/'MimicKit/mimickit')]
    os.chdir(ROOT)
    import numpy as np
    import torch
    import warp as wp
    import yaml
    from util import mp_util
    from learning.base_agent import AgentMode
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from resume import restore, override_actor_learning_rate
    from lossless_runtime import install

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    seed = plan['seed']
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    wp.init(); wp.set_device('cuda:0'); mp_util.init(0, 1, 'cuda:0', 6846)
    cfg, ec, ac = [yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text())
                   for n in ('env', 'engine', 'agent')]
    assert cfg['perturbed_motion']['com2_loss_weight'] == plan['com2_weight']
    ac['actor_optimizer']['learning_rate'] = plan['actor_lr']
    env = PerturbedOmniEnv(cfg, ec, plan['worlds'], 'cuda:0', False)
    agent = OmniPPOAgent(ac, env, 'cuda:0')
    restored = restore(agent, Path(args.checkpoint))
    override_actor_learning_rate(agent, plan['actor_lr'])
    agent._init_train(); agent.set_mode(AgentMode.TRAIN)
    agent._curr_obs, agent._curr_info = agent._reset_envs()
    runtime = install(agent, env)
    sparse, factor = env._engine._dispatch_resources
    assert sparse.hits == dict(velocity=8, derivative=8) and factor.hits == 16
    assert env._engine._cached48_resource.hits == 16
    assert hasattr(env._engine, '_converged_newton_resource')
    for _ in range(plan['warmup_updates']):
        agent._train_iter()
    torch.cuda.synchronize()
    pid = guard = None
    paused = False
    if args.protect_main:
        name = args.protect_main
        assert name == plan['baseline']['run']
        receipt = json.loads((ROOT/(name+'-launch.json')).read_text())
        pid = receipt['pid']
        command = (Path('/proc')/str(pid)/'cmdline').read_bytes()
        assert name.encode() in command and b'pipeline/train.py' in command
        directory = ROOT/'runs'/name
        status = json.loads((directory/'status.json').read_text())
        backup = json.loads((directory/'backup_status.json').read_text())
        assert status['state'] == 'training' and time.time()-status['updated_unix'] < 180
        assert time.time()-backup['verified_unix'] < 600
        # Survives an exception or this benchmark being killed externally.
        code = ('import os,signal,time;from pathlib import Path;time.sleep(60);'
                'p=Path("/proc")/'+repr(str(pid))+'/"cmdline"\n'
                'if p.exists() and '+repr(name.encode())+' in p.read_bytes():'
                'os.kill('+str(pid)+',signal.SIGCONT)')
        guard = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
    rows = []
    began = time.time()
    try:
        if pid:
            os.kill(pid, signal.SIGSTOP); paused = True
            (output/'paused.json').write_text(json.dumps(dict(pid=pid, guard=guard.pid, start=began)))
            time.sleep(.3)
        for index in range(plan['measured_updates']):
            torch.cuda.synchronize(); start = time.perf_counter()
            info = agent._train_iter()
            torch.cuda.synchronize(); seconds = time.perf_counter()-start
            numeric = {}
            for key, value in (info or {}).items():
                if isinstance(value, (float, int)):
                    numeric[key] = value
                elif isinstance(value, torch.Tensor) and value.numel() == 1:
                    numeric[key] = value.item()
            rows.append(dict(update=index, seconds=seconds, info=numeric))
            (output/'progress.json').write_text(json.dumps(dict(updates=rows)))
            assert not pid or time.time()-began < 48, 'Isolated timing window exceeded'
    finally:
        if paused:
            os.kill(pid, signal.SIGCONT)
            (output/'resumed.json').write_text(json.dumps(dict(pid=pid, resumed=time.time(), seconds=time.time()-began)))
        if guard:
            guard.terminate(); guard.wait(timeout=5)
    assert torch.isfinite(agent._curr_obs).all()
    for optimizer in [agent._actor_optimizer, agent._critic_optimizer]:
        assert all(torch.isfinite(p).all() for p in optimizer._param_list)
    device = torch.cuda.get_device_properties(0)
    result = dict(checkpoint=plan['checkpoint'], source=plan['source'], seed=seed,
                  gpu=device.name, compute_capability=[device.major, device.minor],
                  runtime=runtime, restored=restored, updates=rows,
                  mean_seconds=statistics.mean(x['seconds'] for x in rows),
                  median_seconds=statistics.median(x['seconds'] for x in rows),
                  finite=True, finished_unix=time.time(), production_weights_changed=False,
                  scope='Warm complete PPO updates including resets/rewards; excludes periodic evaluation and backup. Not a learning-quality comparison.')
    (output/'complete.json').write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps(dict(gpu=result['gpu'], mean_seconds=result['mean_seconds'], updates=len(rows))), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(traceback.format_exc(), flush=True)
        raise
