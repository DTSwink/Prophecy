"""Exact reference/done graph parity and bounded full-update timing."""
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
from reference_done_graph_probe import make
from mujoco_warp._src import smooth, solver


def main():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    wp.init()
    wp.set_device('cuda:0')
    mp_util.init(0, 1, 'cuda:0', 6830)
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
    candidates = make(e)
    for c in candidates:
        setattr(e, c.method, c)
    # Check boundary states without advancing physics; retain original buffers.
    saved_time=e._time_buf.clone()
    saved_foot=e._final.first_foot.clone()
    all_buffers=[v for c in candidates for v in c.buffers]
    saved_buffers=[v.clone() for v in all_buffers]
    for tick in [0,8,9,49,50,60,79,80,129,130,149,150,200]:
        e._time_buf.fill_(tick/30.)
        e._final.first_foot[::3]=-1
        e._final.first_foot[1::3]=0
        e._final.first_foot[2::3]=50
        for c in candidates:c()
    e._time_buf.copy_(saved_time)
    for v,saved in zip(all_buffers,saved_buffers):v.copy_(saved)
    e._final.first_foot.copy_(saved_foot)
    with torch.no_grad():
        for tick in range(48):
            if tick==32:a.set_mode(AgentMode.TEST)
            if tick==40:a.set_mode(AgentMode.TRAIN)
            action,_=a._decide_action(a._curr_obs,a._curr_info)
            obs,reward,done,info=a._step_env(action)
            assert torch.isfinite(reward).all()
            a._curr_obs,a._curr_info=a._reset_done_envs(done)
    shadow={c.method:dict(comparisons=c.comparisons,elements=c.elements) for c in candidates}
    (OUT/'reference-done-shadow-complete.json').write_text(json.dumps(shadow,indent=2))
    print(json.dumps(shadow),flush=True)
    for c in candidates:c.audit=False
    names=['current','reference_graph','done_graph','reference_and_done_graph']
    def select(index):
        for i,c in enumerate(candidates):
            setattr(e,c.method,c if index&(1<<i) else c.original)
    for index in range(4):
        select(index);a._train_iter()
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
        (OUT / 'reference-done-pause.json').write_text(json.dumps(dict(pid=pid, start=started, guard=guard.pid, limit_seconds=60)))
        time.sleep(.3)
        for index in [0, 1, 2, 3, 3, 2, 1, 0] * 2:
            select(index)
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
        (OUT / 'reference-done-resumed.json').write_text(json.dumps(dict(pid=pid, resumed=time.time(), pause_seconds=time.time() - started)))
    result = dict(checkpoint=checkpoint, shadow=shadow, measurements=rows,
                  source='unchanged reference and done tensor math, captured on TRAIN only; original evaluation path')
    (OUT / 'reference-done-full-complete.json').write_text(json.dumps(result, indent=2))
    print('Full comparison complete', flush=True)
    from probe_concurrent_ppo_full_20261025 import run_existing
    run_existing(a,e,run,checkpoint)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        (OUT / 'reference-done-full-failure.txt').write_text(traceback.format_exc())
        raise
