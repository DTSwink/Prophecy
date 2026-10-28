"""Mock-only source/cache/timer guard audit; never starts or controls a worker."""
import gzip
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
import nn_service as service

ROOT = Path(__file__).resolve().parent
checks = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


request = dict(kind='direction', gait='walk', direction='backward', duration=.2, phase=0)
contract = json.loads((ROOT/'directional-sources.json').read_text())['sources']['walk']['backward']
original_read, original_exists = Path.read_bytes, Path.exists
fake_cached = gzip.compress(json.dumps(dict(marker='mock-only-cache', poses=[])).encode())
changed_source = False


def cache_file(path):
    return path.parent == service.CACHE and path.name.endswith('.json.gz')


def read(path):
    if cache_file(path):
        return fake_cached
    if changed_source and path == Path(contract['source']['path']):
        return b'changed-only-in-memory'
    return original_read(path)


def exists(path):
    return True if cache_file(path) else original_exists(path)


with patch.object(Path, 'read_bytes', read), patch.object(Path, 'exists', exists):
    cached = service.resume(request)
    check('valid immutable source reaches cached result without worker',
          cached['marker'] == 'mock-only-cache' and cached['cache'] == 'identical-seed' and service.worker is None)
    changed_source = True
    rejected = False
    try:
        service.resume(request)
    except ValueError as error:
        rejected = str(error) == 'Immutable directional source changed'
    check('changed source rejected before an existing cache hit', rejected and service.worker is None)

old_timer, current_timer = Mock(), Mock()
service.timer = current_timer
with patch.object(service, '_stop') as stop:
    service._retire(old_timer)
    check('stale retirement cannot stop current worker', not stop.called and service.timer is current_timer)
    service._retire(current_timer)
    check('matching retirement owns cleanup', stop.call_count == 1 and service.timer is None)

service.timer = current_timer
with patch.object(service, '_stop') as stop:
    service.stop_worker()
    check('manual cleanup cancels pending idle timer', current_timer.cancel.call_count == 1 and stop.call_count == 1 and service.timer is None)

check('no worker was started or terminated during guard audit', service.worker is None)
receipt = dict(count=len(checks), checks=checks, scope='Current source tested with cache reads and process-stop function mocked; no running server restart.')
(ROOT/'directional-service-guards-verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
