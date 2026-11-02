"""Real-state shadow audit and bounded full-update comparison of sparse/direct solves."""
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path('/workspace/mimickit_trial')
OUT = ROOT / 'perf-lossless-20261024'
sys.path[:0] = [str(ROOT / 'pipeline'), str(ROOT / 'MimicKit/mimickit')]
os.chdir(ROOT)
import torch
import warp as wp
import yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
from lossless_runtime import install
from fused_backsolve_probe import FusedBacksolve
from blocked_cholesky_probe import BlockedCholesky
from mujoco_warp._src import smooth, solver


@wp.kernel(enable_backward=False)
def compare_rows(width: int, reference: wp.array2d(dtype=float), candidate: wp.array2d(dtype=float),
                 active: wp.array(dtype=bool), masked: int, category: int,
                 maxima: wp.array(dtype=float), counts: wp.array(dtype=int)):
    world = wp.tid()
    if masked != 0 and active[world]:
        return
    error = float(0.0)
    magnitude = float(0.0)
    absolute = float(0.0)
    invalid = int(0)
    for column in range(width):
        a, b = reference[world, column], candidate[world, column]
        if not wp.isfinite(a) or not wp.isfinite(b):
            invalid += 1
        error += (a - b) * (a - b)
        magnitude += a * a
        absolute = wp.max(absolute, wp.abs(a - b))
    wp.atomic_max(maxima, category * 2, absolute)
    wp.atomic_max(maxima, category * 2 + 1, wp.sqrt(error / wp.max(magnitude, 1.e-20)))
    wp.atomic_add(counts, category * 2, 1)
    wp.atomic_add(counts, category * 2 + 1, invalid)


def main():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    wp.init()
    wp.set_device('cuda:0')
    mp_util.init(0, 1, 'cuda:0', 6829)
    cfg, ec, ac = [yaml.safe_load((ROOT / 'prepared' / (n + '_config.yaml')).read_text()) for n in ('env', 'engine', 'agent')]
    e = PerturbedOmniEnv(cfg, ec, 2048, 'cuda:0', False)
    a = OmniPPOAgent(ac, e, 'cuda:0')
    run = ROOT / 'runs' / sys.argv[1]
    checkpoint = json.loads((run / 'backup_status.json').read_text())
    restore(a, run / Path(checkpoint['key']).name)
    a._init_train()
    a.set_mode(AgentMode.TRAIN)
    a._curr_obs, a._curr_info = a._reset_envs()
    install(a, e)
    for _ in range(2):
        a._train_iter()
    eng = e._engine
    s = eng._solver
    m, d = s.mjw_model, s.mjw_data
    sparse, factor = eng._dispatch_resources
    fused = FusedBacksolve(m, d)
    direct = BlockedCholesky(m, d)
    baseline_graph = eng._graph
    scratch = wp.zeros_like(d.qvel)
    fused.apply(m, d, d.qLD, d.qLDiagInv, scratch, scratch)
    compile_ctx = solver.create_solver_context(m, d)
    compile_ctx.done.fill_(True)
    direct.apply(m, d, compile_ctx)
    wp.synchronize()
    print(json.dumps(dict(nv=m.nv, nv_pad=m.nv_pad, baseline_block_dim=m.block_dim.update_gradient_cholesky_blocked)), flush=True)
    maxima = wp.zeros(4, dtype=float)
    counts = wp.zeros(4, dtype=int)
    unmasked = wp.zeros(d.nworld, dtype=bool)
    backsolve_buffers = {width: (wp.zeros((d.nworld, width), dtype=float),
                                wp.zeros((d.nworld, width), dtype=float))
                         for width in {m.nv, m.nv_pad}}
    cholesky_candidate = wp.zeros((d.nworld, m.nv_pad), dtype=float)

    def audit_backsolve(mm, dd, L, D, x, y):
        if mm is not m or dd is not d:
            return fused.original(mm, dd, L, D, x, y)
        source, candidate = backsolve_buffers[y.shape[1]]
        wp.copy(source, y)
        result = fused.original(mm, dd, L, D, x, y)
        fused.apply(mm, dd, L, D, candidate, source)
        wp.launch(compare_rows, dim=d.nworld,
                  inputs=[x.shape[1], x, candidate, unmasked, 0, 0, maxima, counts])
        return result

    def audit_cholesky(mm, dd, ctx):
        result = direct.original(mm, dd, ctx)
        if mm is m and dd is d:
            direct.apply(mm, dd, ctx, cholesky_candidate)
            wp.launch(compare_rows, dim=d.nworld,
                      inputs=[ctx.Mgrad.shape[1], ctx.Mgrad, cholesky_candidate, ctx.done, 1, 1, maxima, counts])
        return result

    # Compile the audit kernel before graph capture.
    wp.launch(compare_rows, dim=d.nworld, inputs=[m.nv, scratch, scratch, unmasked, 0, 0, maxima, counts])
    try:
        # Sparse solve remains unchanged.
        solver._cholesky_factorize_solve = audit_cholesky
        with sparse.capture(), factor.capture():
            eng._build_graphs()
    finally:
        smooth._solve_LD_sparse = fused.original
        solver._cholesky_factorize_solve = direct.original
    counts.zero_()
    maxima.zero_()
    with torch.no_grad():
        for tick in range(80):
            action, _ = a._decide_action(a._curr_obs, a._curr_info)
            obs, reward, done, info = a._step_env(action)
            assert torch.isfinite(reward).all()
            a._curr_obs, a._curr_info = a._reset_done_envs(done)
            if tick % 40 == 39:
                report = dict(ticks=tick + 1, counts=counts.numpy().tolist(), maxima=maxima.numpy().tolist())
                (OUT / 'blocked64-shadow-progress.json').write_text(json.dumps(report, indent=2))
                print(json.dumps(report), flush=True)
    shadow = dict(ticks=80, counts=counts.numpy().tolist(), maxima=maxima.numpy().tolist())
    (OUT / 'blocked64-shadow-complete.json').write_text(json.dumps(shadow, indent=2))
    assert shadow['counts'][1] == 0 and shadow['counts'][3] == 0, shadow
    assert shadow['maxima'][2] == 0 and shadow['maxima'][3] == 0, shadow

    with sparse.capture(), factor.capture(), direct.capture():
        eng._build_graphs()
    candidate_graph = eng._graph
    graphs = [baseline_graph, candidate_graph]
    names = ['baseline_block32', 'blocked64']
    for graph in graphs:
        eng._graph = graph
        a._train_iter()
    assert all(torch.isfinite(parameter).all() for parameter in a._model.parameters())
    torch.cuda.synchronize()
    receipt = json.loads((ROOT / (run.name + '-launch.json')).read_text())
    pid = receipt['pid']
    command = (Path('/proc') / str(pid) / 'cmdline').read_bytes()
    assert run.name.encode() in command and b'pipeline/train.py' in command
    state = json.loads((run / 'status.json').read_text())
    backup = json.loads((run / 'backup_status.json').read_text())
    assert state['state'] == 'training' and time.time() - state['updated_unix'] < 180
    assert time.time() - backup['verified_unix'] < 600
    guard_code = "import os,signal,time;from pathlib import Path;time.sleep(60);p=Path('/proc')/" + repr(str(pid)) + "/'cmdline'\nif p.exists() and " + repr(run.name.encode()) + " in p.read_bytes():os.kill(" + str(pid) + ",signal.SIGCONT)"
    guard = subprocess.Popen([sys.executable, '-c', guard_code], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    rows = []
    started = time.time()
    paused = False
    try:
        os.kill(pid, signal.SIGSTOP)
        paused = True
        (OUT / 'blocked64-pause.json').write_text(json.dumps(dict(pid=pid, start=started, guard=guard.pid, limit_seconds=60)))
        time.sleep(.3)
        for index in [0, 1, 1, 0] * 3:
            eng._graph = graphs[index]
            torch.cuda.synchronize()
            begun = time.perf_counter()
            a._train_iter()
            torch.cuda.synchronize()
            rows.append(dict(variant=names[index], seconds=time.perf_counter() - begun))
            print(json.dumps(rows[-1]), flush=True)
            assert time.time() - started < 50
    finally:
        if paused:
            os.kill(pid, signal.SIGCONT)
        guard.terminate()
        guard.wait(timeout=5)
        (OUT / 'blocked64-resumed.json').write_text(json.dumps(dict(pid=pid, resumed=time.time(), pause_seconds=time.time() - started)))
    result = dict(checkpoint=checkpoint, shadow=shadow, measurements=rows,
                  source='current deployed dispatch baseline; only Cholesky launch block size differs; exact same blocked kernel')
    (OUT / 'blocked64-full-complete.json').write_text(json.dumps(result, indent=2))
    print('Full comparison complete', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        (OUT / 'blocked64-full-failure.txt').write_text(traceback.format_exc())
        raise
