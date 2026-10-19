"""Serve only the newest ten dated comparisons; preserve all historical logs."""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

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
    process = None
    previous = None
    try:
        while True:
            runs = sorted((p for p in args.logdir.resolve().iterdir()
                           if p.is_dir() and DATED_RUN.match(p.name)
                           and any(p.glob('events.out.tfevents.*'))),
                          key=lambda p: p.name, reverse=True)[:args.limit]
            if runs != previous:
                if process is not None:
                    process.terminate()
                    process.wait(timeout=15)
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
            process.terminate()
            process.wait(timeout=15)


if __name__ == '__main__':
    main()
