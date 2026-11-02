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
from cached_cone_probe import CachedCone
from mujoco_warp._src import smooth, solver


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
    eng=e._engine;s=eng._solver;m,d=s.mjw_model,s.mjw_data
    sparse,factor=eng._dispatch_resources
    candidate=CachedCone(m,d)
    baseline_graph=eng._graph
    # Compile kernels outside graph capture using a solver context with every world marked done.
    ctx=solver.create_solver_context(m,d);ctx.done.fill_(True)
    args=[m.opt.impratio_invsqrt,m.dof_tri_row,m.dof_tri_col,d.contact.dist,d.contact.includemargin,
          d.contact.friction,d.contact.dim,d.contact.efc_address,d.contact.worldid,d.efc.J,d.efc.D,d.efc.state,
          d.naconmax,d.nacon,ctx.Jaref,ctx.done,1,1]
    candidate.apply(candidate.original_kernel,(1,m.dof_tri_row.size),args,[ctx.h],audit=True)
    candidate.apply(candidate.original_kernel,(1,m.dof_tri_row.size),args,[ctx.h],audit=False)
    wp.synchronize()
    with sparse.capture(),factor.capture(),candidate.capture(audit=True):eng._build_graphs()
    candidate.counts.zero_();candidate.maxdiff.zero_()
    print('Cone audit ready',flush=True)
    with torch.no_grad():
        for tick in range(40):
            action,_=a._decide_action(a._curr_obs,a._curr_info)
            obs,reward,done,info=a._step_env(action)
            assert torch.isfinite(reward).all()
            a._curr_obs,a._curr_info=a._reset_done_envs(done)
            if tick%10==9:
                result=dict(ticks=tick+1,counts=candidate.counts.numpy().sum(0).tolist(),maxima=candidate.maxdiff.numpy().max(0).tolist())
                (OUT/'cone-shadow-progress.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    shadow=result
    (OUT/'cone-shadow-complete.json').write_text(json.dumps(shadow,indent=2))
    assert shadow['counts'][1]==0 and shadow['counts'][2]==0,shadow
    with sparse.capture(),factor.capture(),candidate.capture():eng._build_graphs()
    optimized_graph=eng._graph
    graphs=[baseline_graph,optimized_graph]
    names=['current','cached_contact_cone']
    for graph in graphs:
        eng._graph=graph;a._train_iter()
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
        (OUT / 'cone-pause.json').write_text(json.dumps(dict(pid=pid, start=started, guard=guard.pid, limit_seconds=60)))
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
        (OUT / 'cone-resumed.json').write_text(json.dumps(dict(pid=pid, resumed=time.time(), pause_seconds=time.time() - started)))
    result = dict(checkpoint=checkpoint, shadow=shadow, measurements=rows,
                  source='current deployed dispatch baseline; original contact cone coefficients calculated once per contact')
    (OUT / 'cone-full-complete.json').write_text(json.dumps(result, indent=2))
    print('Full comparison complete', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        (OUT / 'cone-full-failure.txt').write_text(traceback.format_exc())
        raise
