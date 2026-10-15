"""Finite experiment queue on the existing authorized pod; cannot rent or extend it."""
import json, subprocess, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT = Path('/workspace/mimickit_trial')
OUT = ROOT/'causal_regression'
DEADLINE = 1791953500.0  # 06:51:40 Warsaw, before the 06:57:23 billing guard.
BRANCHES = ['stock', 'frozen', 'norm_only', 'frozen_low_lr', 'stock_low_lr']

def invoke(branch, seed, updates=None, evaluate=None, eval_seed=7719):
    assert time.time() < DEADLINE - 60, 'No room to start another diagnostic'
    args = [str(ROOT/'venv/bin/python'), '-u', str(ROOT/'pipeline/causal_regression.py'),
            '--branch', branch, '--seed', str(seed), '--deadline', str(DEADLINE)]
    if evaluate is None:
        args += ['--updates', str(updates)]
        label = f'repeat_{branch}_{seed}'
    else:
        args += ['--evaluate', str(evaluate), '--eval-seed', str(eval_seed)]
        label = f'eval_{branch}_{seed}_{evaluate}_{eval_seed}'
    with (OUT/(label+'.log')).open('w') as log:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        code = proc.wait(timeout=max(1, DEADLINE-time.time()+30))
    if code: raise RuntimeError(f'{label} failed with {code}; inspect its log')
    return label

def wait_then_evaluate(branch):
    while not (OUT/f'cp150_{branch}_seed9017'/'training.json').exists():
        if time.time() >= DEADLINE-300: raise TimeoutError('First diagnostic did not complete')
        time.sleep(5)
    return invoke(branch, 9017, evaluate=300)

with ThreadPoolExecutor(max_workers=2) as pool:
    first = list(pool.map(wait_then_evaluate, BRANCHES))
(OUT/'first_evaluations_complete.json').write_text(json.dumps(first))
# Independent training seed tests whether the main contrast repeats.
repeat = ['stock', 'frozen', 'frozen_low_lr']
with ThreadPoolExecutor(max_workers=3) as pool:
    trained = list(pool.map(lambda b: invoke(b, 9018, updates=200), repeat))
with ThreadPoolExecutor(max_workers=3) as pool:
    evaluated = list(pool.map(lambda b: invoke(b, 9018, evaluate=200), repeat))
(OUT/'queue_complete.json').write_text(json.dumps(dict(first=first, repeated=trained, evaluated=evaluated)))
print('ALL CONTROLLED TESTS COMPLETE', flush=True)
