"""One bounded CPU policy worker; immutable seed results cached for lab replay."""
import atexit
import concurrent.futures
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parent
MODEL_ROOT = ROOT.parent/'BodyflipLab'
CACHE = ROOT/'.nn-cache'
LOCK = threading.Lock()
worker = None
timer = None
# Keep one sleeping CPU worker through ordinary editing pauses. Thirty seconds
# repeatedly paid the Torch import/model load cost between phase adjustments.
IDLE_SECONDS = 300


def _stop():
    global worker
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


def stop_worker():
    global timer
    with LOCK:
        if timer:
            timer.cancel()
        _stop()
        timer = None


def _retire(expected):
    global timer
    with LOCK:
        if timer is expected:
            _stop()
            timer = None


def _schedule_retirement():
    """Called under LOCK; no polling or inference while the worker is idle."""
    global timer
    if timer:
        timer.cancel()
    retirement = threading.Timer(IDLE_SECONDS, lambda: _retire(retirement))
    timer = retirement
    timer.daemon = True
    timer.start()


atexit.register(stop_worker)


def resume(request):
    global worker, timer
    if request.get('gait') not in ('run', 'walk') or request.get('direction','forward') not in ('forward','backward','left','right'):
        raise ValueError('Invalid terrain NN request')
    if request.get('kind') == 'direction':
        if not .1 <= float(request.get('duration',5)) <= 5 or not 0 <= float(request.get('phase',0)) <= 1:
            raise ValueError('Invalid directional gait controls')
    elif not 2 <= int(request.get('frames',0)) <= 152 or len(request.get('roots', [])) > 200 or len(request.get('seeds', [])) != 2:
        raise ValueError('Two history poses and a bounded root path required')
    encoded = json.dumps(request, separators=(',', ':'), sort_keys=True, allow_nan=False)
    fingerprint = b''.join(p.read_bytes() for p in [ROOT/'nn_worker.py', ROOT/'directional_nn.py', MODEL_ROOT/'locomotion.py', MODEL_ROOT/'models/provenance.json'])
    if request.get('direction', 'forward') != 'forward' or request.get('kind') == 'direction':
        manifest = (ROOT/'directional-sources.json').read_bytes()
        contract = json.loads(manifest)['sources'][request['gait']][request.get('direction','forward')]
        for name in ('source','drawn'):
            item = contract[name]
            if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Immutable directional source changed')
        fingerprint += manifest
    key = hashlib.sha256(fingerprint+encoded.encode()).hexdigest()
    CACHE.mkdir(exist_ok=True)
    path = CACHE/(key+'.json.gz')
    with LOCK:
        if path.exists():
            result = json.loads(gzip.decompress(path.read_bytes()))
            result['cache'] = 'identical-seed'
            if worker is not None and worker.poll() is None:
                _schedule_retirement()
            return result
        if timer:
            timer.cancel()
        try:
            if worker is None or worker.poll() is not None:
                executable = str(Path(sys.executable).with_name('python.exe')) if os.name == 'nt' else sys.executable
                env = dict(os.environ, OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', CUDA_VISIBLE_DEVICES='')
                worker = subprocess.Popen([executable, '-u', str(ROOT/'nn_worker.py')], cwd=ROOT,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, encoding='utf-8', env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            worker.stdin.write(encoded+'\n')
            worker.stdin.flush()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as reader:
                pending = reader.submit(worker.stdout.readline)
                try:
                    line = pending.result(timeout=45)
                except concurrent.futures.TimeoutError:
                    _stop()
                    raise RuntimeError('Terrain NN timed out')
            if not line:
                _stop()
                raise RuntimeError('Terrain NN worker stopped')
            result = json.loads(line)
            if 'error' in result:
                raise ValueError(result['error'])
            result['cache'] = 'inferred'
            path.write_bytes(gzip.compress(json.dumps(result, separators=(',', ':'), allow_nan=False).encode()))
            # Only this service's recomputable responses; compiled graphs retained.
            for old in sorted(CACHE.glob('*.json.gz'), key=lambda p:p.stat().st_mtime, reverse=True)[16:]:
                old.unlink()
            return result
        finally:
            _schedule_retirement()
