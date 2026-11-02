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
from early_done_probe import EarlyDone
from mujoco_warp._src import smooth, solver


def main():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    wp.init()
    wp.set_device('cuda:0')
    mp_util.init(0, 1, 'cuda:0', 6832)
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
    candidate=EarlyDone(m)
    baseline_graph=eng._graph
    context=solver.create_solver_context(m,d)
    with wp.ScopedCapture() as cap:solver._solve(m,d,context)
    solve_baseline=cap.graph
    context_new=solver.create_solver_context(m,d)
    with candidate.capture():
        with wp.ScopedCapture() as cap:solver._solve(m,d,context_new)
    solve_candidate=cap.graph
    outputs=[d.qacc,d.qfrc_constraint,d.efc.Ma,d.efc.force,d.efc.state,d.solver_niter]
    saved=[wp.empty_like(v) for v in outputs]
    rows=[]
    def restore_outputs():
        for v,saved_value in zip(outputs,saved):wp.copy(v,saved_value)
    with torch.no_grad():
        for tick in range(32):
            action,_=a._decide_action(a._curr_obs,a._curr_info)
            obs,reward,done,info=a._step_env(action)
            wp.synchronize()
            for v,saved_value in zip(outputs,saved):wp.copy(saved_value,v)
            results=[]
            for graph in [solve_baseline,solve_baseline,solve_candidate]:
                restore_outputs();wp.capture_launch(graph);wp.synchronize()
                results.append([wp.to_torch(v).clone() for v in outputs])
            restore_outputs();wp.synchronize()
            reference=results[0]
            row={'tick':tick}
            for variant,values in zip(['native_repeat','early_done'],results[1:]):
                fields={}
                for name,index in [('qacc',0),('constraint_force',1),('mass_acceleration',2)]:
                    delta=(values[index]-reference[index]).double()
                    relative=delta.norm(dim=-1)/reference[index].double().norm(dim=-1).clamp_min(1.)
                    fields[name]=dict(max_relative=float(relative.max()),rms_relative=float(relative.square().mean().sqrt()),max_abs=float(delta.abs().max()),finite=bool(torch.isfinite(values[index]).all()))
                active=torch.arange(reference[4].shape[1],device='cuda')[None,:]<wp.to_torch(d.nefc)[:,None]
                fields['active_constraint_state_mismatches']=int(((values[4]!=reference[4])&active).sum())
                fields['solver_iteration_mismatches']=int((values[5]!=reference[5]).sum())
                force_active=torch.arange(reference[3].shape[1],device='cuda')[None,:]<wp.to_torch(d.nefc)[:,None]
                fields['active_force_max_abs']=float(torch.where(force_active,(values[3]-reference[3]).abs(),0.).max())
                row[variant]=fields
            rows.append(row)
            a._curr_obs,a._curr_info=a._reset_done_envs(done)
    shadow=dict(worlds=2048,ticks=32,comparisons=65536,rows=rows)
    def aggregate(variant):
        out={}
        for name in ['qacc','constraint_force','mass_acceleration']:
            out[name]=dict(max_relative=max(row[variant][name]['max_relative'] for row in rows),rms_relative=(sum(row[variant][name]['rms_relative']**2 for row in rows)/len(rows))**.5,finite=all(row[variant][name]['finite'] for row in rows))
        for name in ['active_constraint_state_mismatches','solver_iteration_mismatches']:
            out[name]=sum(row[variant][name] for row in rows)
        return out
    shadow['aggregate']={v:aggregate(v) for v in ['native_repeat','early_done']}
    baseline=shadow['aggregate']['native_repeat'];actual=shadow['aggregate']['early_done']
    checks={}
    for name in ['qacc','constraint_force','mass_acceleration']:
        checks[name]=(actual[name]['finite'] and actual[name]['max_relative']<=max(2.e-5,3.*baseline[name]['max_relative']) and actual[name]['rms_relative']<=max(1.e-6,2.*baseline[name]['rms_relative']))
    for name in ['active_constraint_state_mismatches','solver_iteration_mismatches']:
        checks[name]=actual[name]<=2*baseline[name]
    shadow['checks']=checks
    (OUT/'early-done-shadow-complete.json').write_text(json.dumps(shadow,indent=2))
    print(json.dumps(dict(aggregate=shadow['aggregate'],checks=checks)),flush=True)
    assert all(checks.values()),checks
    with sparse.capture(),factor.capture(),candidate.capture():eng._build_graphs()
    graphs=[baseline_graph,eng._graph]
    names=['current','skip_converged_newton_direction']
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
        (OUT / 'early-done-pause.json').write_text(json.dumps(dict(pid=pid, start=started, guard=guard.pid, limit_seconds=60)))
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
        (OUT / 'early-done-resumed.json').write_text(json.dumps(dict(pid=pid, resumed=time.time(), pause_seconds=time.time() - started)))
    result = dict(checkpoint=checkpoint, shadow=shadow, measurements=rows,
                  source='unchanged Newton/elliptic solve; existing convergence test before final private Hessian/search work')
    (OUT / 'early-done-full-complete.json').write_text(json.dumps(result, indent=2))
    print('Full comparison complete', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        (OUT / 'early-done-full-failure.txt').write_text(traceback.format_exc())
        raise
