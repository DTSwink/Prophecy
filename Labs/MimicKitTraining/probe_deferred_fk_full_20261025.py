"""Audit and time deferred FK on an isolated copy of the live workload."""
import json, os, signal, subprocess, sys, time, traceback
from pathlib import Path

ROOT = Path('/workspace/mimickit_trial')
OUT = ROOT / 'perf-lossless-20261024' / 'deferred-fk'
OUT.mkdir(exist_ok=True)
sys.path[:0] = [str(ROOT/'pipeline'), str(ROOT/'MimicKit/mimickit')]
os.chdir(ROOT)
import torch, warp as wp, yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
from lossless_runtime import install
from deferred_fk_probe import DeferredFK


def main():
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    wp.init(); wp.set_device('cuda:0'); mp_util.init(0, 1, 'cuda:0', 6838)
    cfg, ec, ac = [yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    e = PerturbedOmniEnv(cfg, ec, 2048, 'cuda:0', False)
    a = OmniPPOAgent(ac, e, 'cuda:0'); run = ROOT/'runs'/sys.argv[1]
    cp = json.loads((run/'backup_status.json').read_text())
    restore(a, run/Path(cp['key']).name)
    a._init_train(); a.set_mode(AgentMode.TRAIN); a._curr_obs, a._curr_info = a._reset_envs()
    install(a,e)
    for _ in range(2): a._train_iter()
    eng = e._engine; baseline = eng._graph
    sparse, factor = eng._dispatch_resources
    early = eng._converged_newton_resource
    candidate = DeferredFK(eng)
    with sparse.capture(), factor.capture(), early.capture(), candidate.capture(): eng._build_graphs()
    graphs = [baseline, eng._graph]
    # Recompute the original full body FK into scratch from both final joint states.
    states = [eng._sim_state.raw_state, eng._state_swap_buffer]
    checks = dict(comparisons=0, elements=0, capture_fk_calls=candidate.calls,
                  omitted_calls=candidate.skipped, intermediate_read_check='passed')
    model = eng._sim_model
    outputs = [[wp.empty_like(s.body_q),wp.empty_like(s.body_qd)] for s in states]
    def check():
        for state_index, (s, scratch) in enumerate(zip(states,outputs)):
            wp.launch(candidate.kernel,dim=model.articulation_count,inputs=[
                model.articulation_start,model.joint_articulation,s.joint_q,s.joint_qd,
                model.joint_q_start,model.joint_qd_start,model.joint_type,model.joint_parent,
                model.joint_child,model.joint_X_p,model.joint_X_c,model.joint_axis,
                model.joint_dof_dim,model.body_com],outputs=scratch,device=model.device)
            if state_index == 0:
                # The production adapter corrects child-axis COM velocities after FK.
                adapter = eng._body_velocity
                kernel = adapter.update.__func__.__globals__['reconstruct']
                wp.launch(kernel,dim=adapter.worlds,inputs=[
                    scratch[0].reshape((adapter.worlds,adapter.bodies)),
                    s.joint_qd.reshape((adapter.worlds,adapter.nv)),*adapter.args],
                    outputs=[scratch[1].reshape((adapter.worlds,adapter.bodies))],device=adapter.device)
            for expected,actual in zip(scratch,[s.body_q,s.body_qd]):
                x,y=wp.to_torch(expected),wp.to_torch(actual)
                assert torch.equal(x,y), float((x-y).abs().max())
                checks['comparisons'] += 1; checks['elements'] += x.numel()
    with torch.no_grad():
        for tick in range(40):
            if tick == 32: a.set_mode(AgentMode.TEST)
            if tick == 36: a.set_mode(AgentMode.TRAIN)
            action,_ = a._decide_action(a._curr_obs,a._curr_info)
            obs,reward,done,info = a._step_env(action)
            check()
            a._curr_obs,a._curr_info = a._reset_done_envs(done)
    (OUT/'parity.json').write_text(json.dumps(checks,indent=2))
    for graph in graphs: eng._graph=graph; a._train_iter()
    torch.cuda.synchronize()
    pid=json.loads((ROOT/(run.name+'-launch.json')).read_text())['pid']
    cmd=(Path('/proc')/str(pid)/'cmdline').read_bytes()
    assert run.name.encode() in cmd and b'pipeline/train.py' in cmd
    state=json.loads((run/'status.json').read_text()); backup=json.loads((run/'backup_status.json').read_text())
    assert state['state']=='training' and time.time()-state['updated_unix']<180
    assert time.time()-backup['verified_unix']<600
    code="import os,signal,time;from pathlib import Path;time.sleep(60);p=Path('/proc')/"+repr(str(pid))+"/'cmdline'\nif p.exists() and "+repr(run.name.encode())+" in p.read_bytes():os.kill("+str(pid)+",signal.SIGCONT)"
    guard=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    paused=False; start=time.time(); rows=[]
    try:
        os.kill(pid,signal.SIGSTOP); paused=True
        (OUT/'pause.json').write_text(json.dumps(dict(pid=pid,guard=guard.pid,start=start)))
        time.sleep(.3)
        for index in [0,1,1,0]*3:
            eng._graph=graphs[index]; torch.cuda.synchronize(); t=time.perf_counter()
            a._train_iter(); torch.cuda.synchronize()
            rows.append(dict(variant=['current','deferred_fk'][index],seconds=time.perf_counter()-t))
            assert time.time()-start<50
    finally:
        if paused: os.kill(pid,signal.SIGCONT)
        guard.terminate(); guard.wait(timeout=5)
        (OUT/'resumed.json').write_text(json.dumps(dict(pid=pid,resumed=time.time(),seconds=time.time()-start)))
    (OUT/'complete.json').write_text(json.dumps(dict(checkpoint=cp,checks=checks,measurements=rows),indent=2))


if __name__=='__main__':
    try: main()
    except Exception:
        (OUT/'failure.txt').write_text(traceback.format_exc())
        raise
