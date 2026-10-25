"""Bounded, single-worker landing inference; release Torch after 30 idle seconds."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parent
CACHE = ROOT/'.resume-cache'
LOCK = threading.Lock()
worker = None
timer = None


def stop_worker():
    global worker, timer
    with LOCK:
        if worker is not None:
            worker.terminate()
            try:
                worker.wait(timeout=3)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()
            worker.stdin.close()
            worker.stdout.close()
            worker = None
        timer = None


def resume(request):
    global worker, timer
    encoded = json.dumps(request, separators=(',', ':'), sort_keys=True, allow_nan=False)
    fingerprint = (ROOT/'resume_locomotion.py').read_bytes()+(ROOT/'models/provenance.json').read_bytes()
    key = hashlib.sha256(fingerprint+encoded.encode()).hexdigest()
    CACHE.mkdir(exist_ok=True)
    path = CACHE/(key+'.json.gz')
    with LOCK:
        if path.exists():
            result = json.loads(gzip.decompress(path.read_bytes()))
            result['cache'] = 'landing-seed'
            return result
        if timer:
            timer.cancel()
        try:
            if worker is None or worker.poll() is not None:
                env = dict(os.environ, OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', CUDA_VISIBLE_DEVICES='')
                # This is the lab's existing Python environment, not an engine process.
                executable = str(Path(sys.executable).with_name('python.exe')) if os.name == 'nt' else sys.executable
                worker = subprocess.Popen([executable, '-u', str(ROOT/'resume_locomotion.py')], cwd=ROOT,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, encoding='utf-8', env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            worker.stdin.write(encoded+'\n')
            worker.stdin.flush()
            line = worker.stdout.readline()
            if not line:
                raise RuntimeError('Landing NN worker stopped')
            result = json.loads(line)
            if 'error' in result:
                raise ValueError(result['error'])
            path.write_bytes(gzip.compress(json.dumps(result, separators=(',', ':'), allow_nan=False).encode()))
            # Bound retained cache storage; no unrelated files are touched.
            entries = sorted(CACHE.glob('*.json.gz'), key=lambda p:p.stat().st_mtime, reverse=True)
            for old in entries[16:]:
                old.unlink()
            return result
        finally:
            timer = threading.Timer(30, stop_worker)
            timer.daemon = True
            timer.start()
