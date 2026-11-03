"""Serve only the newest ten dated comparisons; preserve all historical logs."""

# These local I/O/viewer services do not need numerical worker pools.
# Set before NumPy/SciPy/TensorBoard imports: otherwise each process reserves
# hundreds of MB for threads on Windows. This does not change GPU training.
import os
for _thread_variable in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_thread_variable] = '1'

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from local_process import ServiceLock, stop_child_tree

ROOT = Path(__file__).resolve().parents[2]
DATED_RUN = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}(?:-\d{2})?_')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--logdir', type=Path, default=ROOT/'Saved/MimicKit/TensorBoardRuns')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--port', type=int, default=8035)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error('--limit must be positive')
    with ServiceLock(ROOT/'Saved/MimicKit'/f'tensorboard-{args.port}.lock'):
        serve(args)


def serve(args):
    process = None
    previous = None
    try:
        while True:
            hidden_file = args.logdir / 'hidden-runs.json'
            hidden = set(json.loads(hidden_file.read_text()) if hidden_file.exists() else [])
            runs = sorted((p for p in args.logdir.resolve().iterdir()
                           if p.is_dir() and DATED_RUN.match(p.name)
                           and p.name not in hidden
                           and any(p.glob('events.out.tfevents.*'))),
                          key=lambda p: p.name, reverse=True)[:args.limit]
            if runs != previous:
                if process is not None:
                    stop_child_tree(process)
                    process = None
                if runs:
                    command = [sys.executable, '-m', 'tensorboard.main',
                               '--logdir_spec', ','.join(f'{p.name}:{p}' for p in runs),
                               '--host', '127.0.0.1', '--port', str(args.port),
                               '--reload_interval', '15', '--load_fast', 'false']
                    process = subprocess.Popen(command)
                    print(json.dumps(dict(visible_runs=[p.name for p in runs],
                                          server_pid=process.pid, port=args.port)), flush=True)
                previous = runs
            if process is not None and process.poll() is not None:
                raise RuntimeError(f'TensorBoard exited with code {process.returncode}')
            time.sleep(15)
    finally:
        if process is not None and process.poll() is None:
            stop_child_tree(process)


if __name__ == '__main__':
    main()
