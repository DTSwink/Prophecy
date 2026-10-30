"""Cache eviction integration with a fake inference pipe; no models/live state."""
import io, json, tempfile
from pathlib import Path
import nn_service as service

class Worker:
    def __init__(self):
        self.stdin = io.StringIO()
        self.stdout = self
        self.calls = 0
    def poll(self):
        return None
    def readline(self):
        self.calls += 1
        return json.dumps(dict(kind='surface',steps=[],appendedInferences=0))+'\n'

old = service.CACHE, service.worker, service._schedule_retirement
try:
    with tempfile.TemporaryDirectory(prefix='footik-response-cache-') as folder:
        service.CACHE = Path(folder)
        service.worker = worker = Worker()
        service._schedule_retirement = lambda: None
        (service.CACHE/'retained.pt').write_bytes(b'compiled graph')
        seed = dict(gait='run',frames=2,roots=[],seeds=[{},{}])
        service.resume(seed)
        for i in range(17):
            request = dict(seed,kind='surface',endTime=.1,totalDuration=5,case=i)
            service.resume(request)
        count = worker.calls
        assert service.resume(seed)['cache'] == 'identical-seed'
        assert worker.calls == count, 'Surface tuning must not evict the starting seed'
        files = list(service.CACHE.glob('surface-*.json.gz'))
        assert len(files) == 16
        latest = max(files,key=lambda p:p.stat().st_mtime)
        legacy = latest.with_name(latest.name.removeprefix('surface-'))
        latest.replace(legacy)
        assert service.resume(request)['cache'] == 'identical-prefix'
        assert latest.exists() and not legacy.exists() and worker.calls == count
        assert (service.CACHE/'retained.pt').read_bytes() == b'compiled graph'
        print(json.dumps(dict(passed=True,seedRetainedAfterEdits=17,surfaceBudget=16,legacyMigrated=True)))
finally:
    service.CACHE, service.worker, service._schedule_retirement = old
