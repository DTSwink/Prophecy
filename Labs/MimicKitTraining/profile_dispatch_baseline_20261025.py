"""Bounded attribution of the deployed dispatch runtime on the existing GPU."""
import json, os, signal, subprocess, sys, time, traceback
from pathlib import Path

ROOT = Path('/workspace/mimickit_trial')
OUT = ROOT / 'perf-lossless-20261024' / 'dispatch-baseline'
OUT.mkdir(exist_ok=True)
sys.path[:0] = [str(ROOT / 'pipeline'), str(ROOT / 'MimicKit/mimickit')]
os.chdir(ROOT)
import torch, warp as wp, yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
from lossless_runtime import install
from profile_training import run_profiled_update


def main():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    wp.init(); wp.set_device('cuda:0'); mp_util.init(0, 1, 'cuda:0', 6837)
    cfg, ec, ac = [yaml.safe_load((ROOT / 'prepared' / (n + '_config.yaml')).read_text())
                   for n in ('env', 'engine', 'agent')]
    e = PerturbedOmniEnv(cfg, ec, 2048, 'cuda:0', False)
    a = OmniPPOAgent(ac, e, 'cuda:0')
    run = ROOT / 'runs' / sys.argv[1]
    cp = json.loads((run / 'backup_status.json').read_text())
    restore(a, run / Path(cp['key']).name)
    a._init_train(); a.set_mode(AgentMode.TRAIN)
    a._curr_obs, a._curr_info = a._reset_envs()
    runtime = install(a, e)
    for _ in range(2): a._train_iter()
    torch.cuda.synchronize()
    receipt = json.loads((ROOT / (run.name + '-launch.json')).read_text())
    pid = receipt['pid']
    cmd = (Path('/proc') / str(pid) / 'cmdline').read_bytes()
    assert run.name.encode() in cmd and b'pipeline/train.py' in cmd
    status = json.loads((run / 'status.json').read_text())
    backup = json.loads((run / 'backup_status.json').read_text())
    assert status['state'] == 'training' and time.time() - status['updated_unix'] < 180
    assert time.time() - backup['verified_unix'] < 600
    code = "import os,signal,time;from pathlib import Path;time.sleep(60);p=Path('/proc')/" + repr(str(pid)) + "/'cmdline'\nif p.exists() and " + repr(run.name.encode()) + " in p.read_bytes():os.kill(" + str(pid) + ",signal.SIGCONT)"
    guard = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    start = time.time(); paused = False
    try:
        os.kill(pid, signal.SIGSTOP); paused = True
        (OUT / 'pause.json').write_text(json.dumps(dict(pid=pid, guard=guard.pid, start=start)))
        time.sleep(.3)
        normal = []
        for _ in range(3):
            torch.cuda.synchronize(); t = time.perf_counter(); a._train_iter(); torch.cuda.synchronize()
            normal.append(time.perf_counter() - t)
        run_profiled_update(a, a._train_iter, OUT, 0)
        with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,
                                              torch.profiler.ProfilerActivity.CUDA]) as trace:
            a._train_iter(); torch.cuda.synchronize()
        table = trace.key_averages()
        ops = [dict(name=x.key, calls=x.count, cpu_us=x.self_cpu_time_total,
                    cuda_us=x.self_device_time_total) for x in table]
        (OUT / 'operators.json').write_text(json.dumps(ops))
        trace.export_chrome_trace(str(OUT / 'trace.json.gz'))
        assert time.time() - start < 55, 'Profile exceeded isolated window; do not use timings'
    finally:
        if paused: os.kill(pid, signal.SIGCONT)
        guard.terminate(); guard.wait(timeout=5)
        (OUT / 'resumed.json').write_text(json.dumps(dict(pid=pid, resumed=time.time(), seconds=time.time()-start)))
    (OUT / 'complete.json').write_text(json.dumps(dict(checkpoint=cp, runtime=runtime,
        normal_update_seconds=normal, seconds=time.time()-start), indent=2))


if __name__ == '__main__':
    try: main()
    except Exception:
        (OUT / 'failure.txt').write_text(traceback.format_exc())
        raise
