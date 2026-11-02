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


import copy, types
from kl_guard import Snapshot
from policy_dispatch_probe import shared_action, SelectedMinibatches
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
    original_action=a._decide_action
    candidate_action=types.MethodType(shared_action,a)
    selected=SelectedMinibatches(a)
    checks=[]
    def eq(x,y):
        if isinstance(x,torch.Tensor): return torch.equal(x,y)
        if isinstance(x,dict): return x.keys()==y.keys() and all(eq(x[k],y[k]) for k in x)
        if isinstance(x,(list,tuple)): return len(x)==len(y) and all(eq(i,j) for i,j in zip(x,y))
        return x==y
    # Compare the entire PPO update on exactly the same rollout and sample order.
    snapshots={k:Snapshot(getattr(a,'_'+k+'_optimizer')) for k in ['actor','critic']}
    sample_buf=a._exp_buffer._sample_buf.clone();sample_head=a._exp_buffer._sample_buf_head
    rng=torch.cuda.get_rng_state()
    expected_info=a._update_model()
    expected_model=copy.deepcopy(a._model.state_dict())
    expected_optim={k:copy.deepcopy(getattr(a,'_'+k+'_optimizer')._optimizer.state_dict()) for k in snapshots}
    expected_rng=torch.cuda.get_rng_state();expected_buf=a._exp_buffer._sample_buf.clone();expected_head=a._exp_buffer._sample_buf_head
    for snap in snapshots.values():snap.restore()
    a._exp_buffer._sample_buf.copy_(sample_buf);a._exp_buffer._sample_buf_head=sample_head;torch.cuda.set_rng_state(rng)
    selected.install()
    actual_info=a._update_model()
    update_check=dict(metrics=eq(expected_info,actual_info),weights=eq(expected_model,a._model.state_dict()),
        optimizer=eq(expected_optim,{k:getattr(a,'_'+k+'_optimizer')._optimizer.state_dict() for k in snapshots}),
        rng=eq(expected_rng,torch.cuda.get_rng_state()),sample_order=eq(expected_buf,a._exp_buffer._sample_buf) and expected_head==a._exp_buffer._sample_buf_head)
    (OUT/'policy-dispatch-update-parity.json').write_text(json.dumps(update_check,indent=2))
    assert all(update_check.values()),update_check
    selected.uninstall()
    for mode in [AgentMode.TRAIN,AgentMode.TEST,AgentMode.TRAIN]:
        a.set_mode(mode)
        with torch.no_grad():
            for tick in range(32):
                saved=e._pending_phase.clone();rng=torch.cuda.get_rng_state()
                expected=original_action(a._curr_obs,a._curr_info)
                expected_phase=e._pending_phase.clone();expected_rng=torch.cuda.get_rng_state()
                e._pending_phase.copy_(saved);torch.cuda.set_rng_state(rng)
                actual=candidate_action(a._curr_obs,a._curr_info)
                check=dict(mode=str(mode),tick=tick,action_info_exact=eq(expected,actual),
                    phase_exact=eq(expected_phase,e._pending_phase),rng_exact=eq(expected_rng,torch.cuda.get_rng_state()),
                    phase_max_error=float((expected_phase-e._pending_phase).abs().max()))
                checks.append(check)
                obs,reward,done,info=a._step_env(expected[0]);a._curr_obs,a._curr_info=a._reset_done_envs(done)
    (OUT/'policy-dispatch-action-parity.json').write_text(json.dumps(checks,indent=2))
    shared_ok=all(c['phase_exact'] and c['action_info_exact'] and c['rng_exact'] for c in checks)
    print(json.dumps(dict(shared_action_exact=shared_ok,phase_max_error=max(c['phase_max_error'] for c in checks),update_check=update_check)),flush=True)
    def select(index):
        selected.install() if index else selected.uninstall()
        a._decide_action=candidate_action if index==2 else original_action
    names=['current','selective_minibatches']+(['selective_and_shared_action'] if shared_ok else [])
    for index in range(len(names)):
        select(index);a._train_iter()
    torch.cuda.synchronize()
    receipt=json.loads((ROOT/(run.name+'-launch.json')).read_text());pid=receipt['pid']
    cmd=(Path('/proc')/str(pid)/'cmdline').read_bytes();assert run.name.encode() in cmd and b'pipeline/train.py' in cmd
    status=json.loads((run/'status.json').read_text());backup=json.loads((run/'backup_status.json').read_text())
    assert status['state']=='training' and time.time()-status['updated_unix']<180
    assert time.time()-backup['verified_unix']<600
    code="import os,signal,time;from pathlib import Path;time.sleep(60);p=Path('/proc')/"+repr(str(pid))+"/'cmdline'\nif p.exists() and "+repr(run.name.encode())+" in p.read_bytes():os.kill("+str(pid)+",signal.SIGCONT)"
    guard=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    rows=[];start=time.time();paused=False
    try:
        os.kill(pid,signal.SIGSTOP);paused=True
        (OUT/'policy-dispatch-pause.json').write_text(json.dumps(dict(pid=pid,guard=guard.pid,start=start)))
        time.sleep(.3)
        sequence=([0,1,2,2,1,0]*2) if shared_ok else ([0,1,1,0]*3)
        for index in sequence:
            select(index);torch.cuda.synchronize();t=time.perf_counter();a._train_iter();torch.cuda.synchronize()
            rows.append(dict(variant=names[index],seconds=time.perf_counter()-t));print(json.dumps(rows[-1]),flush=True)
            assert time.time()-start<50
    finally:
        if paused:os.kill(pid,signal.SIGCONT)
        guard.terminate();guard.wait(timeout=5)
        (OUT/'policy-dispatch-resumed.json').write_text(json.dumps(dict(pid=pid,resumed=time.time(),pause_seconds=time.time()-start)))
    result=dict(checkpoint=checkpoint,update_check=update_check,shared_action_exact=shared_ok,phase_max_error=max(c['phase_max_error'] for c in checks),measurements=rows)
    (OUT/'policy-dispatch-complete.json').write_text(json.dumps(result,indent=2))

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'policy-dispatch-failure.txt').write_text(traceback.format_exc());raise
