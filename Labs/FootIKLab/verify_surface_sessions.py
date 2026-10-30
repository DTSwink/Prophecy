"""Offline bounded surface wire/checkpoint test; recorded NN responses only."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import hashlib

import nn_worker  # Installs the read-only frozen-model import paths.
import surface_nn as sn
import nn_service
from locomotion import torch

ROOT = Path(__file__).resolve().parent
checks = []
def check(name, value, measured=None):
    checks.append(dict(name=name, passed=bool(value), measured=measured))
    if not value:
        raise AssertionError(name)

fixture = json.loads(gzip.decompress((ROOT/'snapshots/slide-live-5.json.gz').read_bytes()))
recorded = fixture['response']['steps']
calls = []
RealStream = sn.Stream
class RecordedStream:
    def __init__(self, owner, verify=False):
        self.index = 0
        self.policy_seconds = 0
        self.max_feature_error = 0
    def step(self, request):
        calls.append(self.index)
        result = recorded[self.index]
        self.index += 1
        return result
    def checkpoint(self):
        return dict(index=self.index)
    def restore(self, state):
        self.index = state['index']

class Owner:
    device = torch.device('cpu')
owner = Owner()
original = copy.deepcopy(fixture['request'])
original.update(sourceVersion=sn.source_version(), totalDuration=5, endTime=1/30)
# Preserve snapshots byte-for-byte; all session persistence is disposable.
sn.Stream = RecordedStream
try:
    with tempfile.TemporaryDirectory(prefix='footik-session-test-') as temp:
        sessions = sn.SurfaceSessions()
        sessions.folder = Path(temp)
        try:
            first = sessions.process(owner, original)
            token = first['sessionId']
            check('Exact first30Hz boundary emits no unused policy target',first['generatedThrough']==1/30 and len(first['steps'])==0 and len(calls)==0)
            request = dict(original, sessionId=token, endTime=.05)
            second = sessions.process(owner, request)
            check('Partial interval uses one necessary interpolation endpoint',second['appendedInferences']==1 and len(calls)==1 and second['generatedThrough']==.05)
            one = sessions.process(owner, dict(request,endTime=1))
            prefix = copy.deepcopy(one['steps'])
            check('Extension reuses policy prefix',one['steps'][0]==second['steps'][0] and len(calls)==len(one['steps']))
            count = len(calls)
            again = sessions.process(owner, dict(request,endTime=1))
            shrink = sessions.process(owner, dict(request,endTime=.25))
            check('Same endpoint and shrinking are zero-inference',len(calls)==count and again['appendedInferences']==shrink['appendedInferences']==0)
            check('Generated through remains the retained prefix',shrink['generatedThrough']==1)
            check('No inference beyond requested end',all(w['frame']<60 for w in one['diagnostics']['coupling']['windows']))
            old_peer = sessions.active[token].child
            sessions.close()
            check('Closing retained session retires its peer',old_peer.poll() is not None)
            restored = sessions.process(owner, dict(request,endTime=1.5))
            check('Retirement restores only cached prefix, infers new tail',restored['restored'] and len(calls)-count==restored['appendedInferences'])
            check('Restored policy prefix is byte-identical',restored['steps'][:len(prefix)]==prefix)
            check('Recurrent counter restores at exact policy boundary',calls[count]==len(prefix))
            final = sessions.process(owner,dict(request,endTime=2))
            fresh = sessions.process(owner,dict(original,endTime=2,fixtureCase='fresh'))
            check('Split/reloaded and one-pass responses are identical',final['steps']==fresh['steps'])
            check('Split/reloaded root windows are identical',final['diagnostics']['coupling']['windows']==fresh['diagnostics']['coupling']['windows'])
            def poses(result):
                import base64
                frames = []
                for batch in result['frameBatches']:
                    check('Pose batch is contiguous', batch['start'] == len(frames))
                    part = json.loads(gzip.decompress(base64.b64decode(batch['data'])))
                    check('Pose count matches batch', len(part) == batch['count'])
                    frames.extend(part)
                return frames
            final_poses, fresh_poses = poses(final), poses(fresh)
            check('Split/restored compressed poses equal one-pass exactly', final_poses == fresh_poses)
            check('Pose batches stop at requested end', len(final_poses) == 241)
            peer = sessions.active[token].child
            sessions.process(owner,dict(original,endTime=.05,fixtureCase='third'))
            check('Only two resident sessions; idle peer reused without another process',len(sessions.active)==2 and peer.poll() is None and any(s.child is peer for s in sessions.active.values()))
            count = len(calls)
            restored_again = sessions.process(owner,dict(request,endTime=2))
            check('LRU eviction restores a saved completed prefix without NN calls',restored_again['restored'] and restored_again['appendedInferences']==0 and len(calls)==count)
            check('Reused peer resets all motion state', poses(restored_again) == fresh_poses)
            try:
                sessions.process(owner,dict(request,sessionId='../invalid'))
                check('Malformed opaque key rejected',False)
            except ValueError:
                check('Malformed opaque key rejected',True)
        finally:
            sessions.close()
finally:
    sn.Stream = RealStream

# Exact tensor persistence preserves both histories; no encode/decode round trip.
a = object.__new__(RealStream)
a.owner = owner
a.initialized = True
a.policy_seconds = 1.25
for i,name in enumerate(('previous','current','prev_upper','cur_upper','prev_pelvis','cur_pelvis','base')):
    setattr(a,name,torch.arange(7+i,dtype=torch.float32).reshape(1,-1)/7)
b = object.__new__(RealStream)
b.owner = owner
b.restore(json.loads(json.dumps(a.checkpoint())))
check('All seven recurrent tensors round-trip exactly',all(torch.equal(getattr(a,n),getattr(b,n)) for n in ('previous','current','prev_upper','cur_upper','prev_pelvis','cur_pelvis','base')))

class BusyLock:
    def acquire(self,timeout):
        self.timeout=timeout
        return False
lock = nn_service.LOCK
busy = BusyLock()
nn_service.LOCK = busy
try:
    try:
        with nn_service.request_lock():
            pass
        check('Busy queue is bounded',False)
    except RuntimeError as error:
        check('Busy queue is bounded and error is actionable',busy.timeout==12 and 'busy' in str(error))
finally:
    nn_service.LOCK = lock

report = dict(passed=True,checks=checks,sourceVersion=sn.source_version(),scope='Recorded inference responses; no live service, new inference, or user scene changes.')
(ROOT/'snapshots/surface-session-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=True,checks=len(checks),sourceVersion=report['sourceVersion'])))
