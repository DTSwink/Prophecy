"""Run pinned upstream T1 unchanged, with local logging and a graceful deadline.

No Prophecy environment, controller, reward, constraint or model imports.
The dependency runtime is the existing isolated Windows installation; it is
not claimed to reproduce the upstream Python/CUDA dependency lockfile.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'Saved/Robotics'
sys.path.insert(0, str(OUT/'vendor/mjlab_playground/src'))

import torch
import warp as wp
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.utils.os import dump_yaml
from mjlab.utils.torch import configure_torch_backends
from mjlab_playground.getup.config.t1.env_cfgs import booster_t1_getup_env_cfg
from mjlab_playground.getup.config.t1.rl_cfg import booster_t1_getup_ppo_runner_cfg
from replay_upstream import UpstreamReplay


class Stopped(Exception):
    pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', default='upstream_t1_control_01')
    p.add_argument('--worlds', type=int, default=4096)
    p.add_argument('--resume', type=Path)
    a = p.parse_args()
    run = OUT/'runs'/a.run
    if run.exists() and not a.resume:
        raise ValueError('Use a fresh run directory; existing evidence is preserved')
    run.mkdir(parents=True, exist_ok=bool(a.resume))
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    configure_torch_backends()
    wp.init()
    task = booster_t1_getup_env_cfg()
    agent = booster_t1_getup_ppo_runner_cfg()
    task.scene.num_envs = a.worlds
    task.seed = agent.seed
    agent.logger = 'tensorboard'
    agent.upload_model = False
    agent.run_name = a.run
    cfg = asdict(agent)
    if not a.resume:
        dump_yaml(run/'params/env.yaml', asdict(task))
        dump_yaml(run/'params/agent.yaml', cfg)
    versions = {n: importlib.metadata.version(n) for n in ('torch', 'mujoco', 'mujoco-warp', 'warp-lang', 'rsl-rl-lib')}
    sources = {}
    for name in ('mjlab', 'mjlab_playground'):
        sources[name] = subprocess.check_output(['git', '-C', str(OUT/'vendor'/name), 'rev-parse', 'HEAD'], text=True).strip()
    contract = {'task': 'Mjlab-Getup-Flat-Booster-T1', 'sources': sources, 'versions': versions,
                'python': sys.version, 'worlds': a.worlds, 'updates': agent.max_iterations,
                'steps_per_update_per_world': agent.num_steps_per_env,
                'transition_budget': a.worlds*agent.max_iterations*agent.num_steps_per_env,
                'changes_from_task_defaults': ['world count from README example', 'local tensorboard logging; no upload'],
                'dependency_lockfile_reproduction': False}
    if a.resume:
        saved_contract = json.loads((run/'contract.json').read_text())
        if saved_contract != contract:
            raise ValueError('Resume contract differs from the original upstream run')
    else:
        (run/'contract.json').write_text(json.dumps(contract, indent=2), encoding='utf-8')
    previous_wall = json.loads((run/'status.json').read_text())['elapsed_wall_seconds'] if a.resume else 0
    start = time.time()
    raw = ManagerBasedRlEnv(cfg=task, device='cuda:0')
    env = RslRlVecEnvWrapper(raw, clip_actions=agent.clip_actions)

    class Runner(MjlabOnPolicyRunner):
        def save(self, path, infos=None):
            super().save(path, {**(infos or {}), 'upstream_control': contract})
            status = {'iteration': self.current_learning_iteration,
                      'policy_steps': raw.common_step_counter,
                      'training_transitions': raw.common_step_counter*a.worlds,
                      'checkpoint': str(Path(path).resolve()), 'updated_unix': time.time(),
                      'elapsed_wall_seconds': previous_wall+time.time()-start}
            (run/'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')

    runner = Runner(env, cfg, str(run), device='cuda:0')
    if a.resume:
        infos = runner.load(str(a.resume), map_location='cuda:0')
        if infos['upstream_control'] != contract:
            raise ValueError('Checkpoint task contract differs')
        runner.current_learning_iteration += 1
        runner.logger.tot_timesteps = raw.common_step_counter*a.worlds
        print(f'Resumed update {runner.current_learning_iteration}, {raw.common_step_counter*a.worlds} transitions; optimizer/curriculum restored', flush=True)
    replay = UpstreamReplay(raw, a.run)
    last_checkpoint = str(a.resume) if a.resume else ''
    published_update = -1
    original_step = env.step
    deadline = datetime(2026, 10, 14, 5, 10, tzinfo=timezone.utc).timestamp()

    def bounded_step(actions):
        nonlocal published_update, last_checkpoint
        if raw.common_step_counter and raw.common_step_counter % agent.num_steps_per_env == 0:
            if replay.count and (published_update < 0 or runner.current_learning_iteration-published_update >= 10):
                status_path = run/'status.json'
                if status_path.exists():
                    last_checkpoint = json.loads(status_path.read_text())['checkpoint']
                replay.publish(runner.current_learning_iteration, last_checkpoint)
                published_update = runner.current_learning_iteration
            if (run/'stop.request').exists() or time.time() >= deadline:
                runner.save(str(run/f'model_{runner.current_learning_iteration}.pt'))
                raise Stopped('Saved at completed update boundary')
        result = original_step(actions)
        replay.capture()
        return result

    env.step = bounded_step
    try:
        runner.learn(num_learning_iterations=agent.max_iterations-runner.current_learning_iteration, init_at_random_ep_len=True)
        replay.publish(runner.current_learning_iteration, run/f'model_{runner.current_learning_iteration}.pt')
        (run/'completed.json').write_text(json.dumps({'finished': True, 'wall_seconds': time.time()-start}))
    except Stopped as e:
        print(str(e), flush=True)
    finally:
        replay.close()
        env.close()


if __name__ == '__main__':
    main()
