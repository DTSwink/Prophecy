"""Disposable policy rollouts measuring convergence tails; never changes production."""
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path('/workspace/mimickit_trial')
OUT = ROOT / 'perf-lossless-20261024'
sys.path[:0] = [str(ROOT / 'pipeline'), str(ROOT / 'MimicKit/mimickit')]
os.chdir(ROOT)
import numpy as np
import torch
import warp as wp
import yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
from lossless_runtime import install


def main():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    wp.init()
    wp.set_device('cuda:0')
    mp_util.init(0, 1, 'cuda:0', 6828)
    cfg, ec, ac = [yaml.safe_load((ROOT / 'prepared' / (n + '_config.yaml')).read_text())
                   for n in ('env', 'engine', 'agent')]
    e = PerturbedOmniEnv(cfg, ec, 2048, 'cuda:0', False)
    a = OmniPPOAgent(ac, e, 'cuda:0')
    restore(a, ROOT / 'resume.zip')
    a._init_train()
    a.set_mode(AgentMode.TRAIN)
    a._curr_obs, a._curr_info = a._reset_envs()
    install(a, e)
    eng = e._engine
    solver = eng._solver
    d = solver.mjw_data
    copies = [wp.zeros_like(d.solver_niter) for _ in range(eng._sim_steps)]
    original = solver.step
    slots = []

    def step(*args, **kwargs):
        result = original(*args, **kwargs)
        slot = len(slots)
        assert slot < len(copies)
        wp.copy(copies[slot], d.solver_niter)
        slots.append(slot)
        return result

    sparse, factor = eng._dispatch_resources
    try:
        solver.step = step
        with sparse.capture(), factor.capture():
            eng._build_graphs()
    finally:
        solver.step = original
    assert len(slots) == 8
    results = []
    started = time.perf_counter()
    with torch.no_grad():
        for tick in range(160):
            action, _ = a._decide_action(a._curr_obs, a._curr_info)
            obs, reward, done, info = a._step_env(action)
            assert torch.isfinite(reward).all()
            a._curr_obs, a._curr_info = a._reset_done_envs(done)
            results.append(np.stack([x.numpy() for x in copies]))
            if tick % 40 == 39:
                print(json.dumps(dict(ticks=tick + 1, elapsed_seconds=time.perf_counter() - started)), flush=True)
    samples = np.stack(results)
    maxima = samples.max(axis=2)
    report = dict(worlds=2048, ticks=160, substeps=8, physics_states=int(samples.size),
                  graph_conditional=bool(solver.mjw_model.opt.graph_conditional),
                  max_iterations=solver.mjw_model.opt.iterations,
                  parallel_linesearch=bool(solver.mjw_model.opt.ls_parallel),
                  per_world_quantiles=np.quantile(samples, [0, .5, .9, .95, .99, .999, 1]).tolist(),
                  batch_max_quantiles=np.quantile(maxima, [0, .5, .9, .95, .99, 1]).tolist(),
                  mean_iterations=float(samples.mean()),
                  mean_batch_max=float(maxima.mean()),
                  fraction_at_cap=float(np.mean(samples == solver.mjw_model.opt.iterations)),
                  elapsed_seconds=time.perf_counter() - started,
                  caveat='Diagnostic rollout shares GPU with training; elapsed time is not a throughput comparison.')
    np.savez_compressed(OUT / 'solver-tail-counts.npz', iterations=samples)
    (OUT / 'solver-tail-complete.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        (OUT / 'solver-tail-failure.txt').write_text(traceback.format_exc())
        raise
