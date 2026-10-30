"""One causal policy stream; shared JS owns the root physics and foot solver."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import inspect
import warnings
import gzip
import uuid
import tempfile
from collections import OrderedDict

from locomotion import torch, runtime_data, upper_data, tl
from directional_nn import decode_policy_rows
from nn_worker import encode_lower, compiled_step, inference_execution, policy_graph_fingerprint

ROOT = Path(__file__).resolve().parent
FILES = ('surface.js', 'surface-coupling.js', 'surface_driver.cjs', 'surface_nn.py',
         'footik.js', 'support.js', 'recovery.js', 'slide-joints.js', 'slide-entry.js','slide-arms.js')


class DecodeStep(torch.nn.Module):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def forward(self, lower, upper, pelvis, roots, bases, headings):
        return decode_policy_rows(self.owner, self.owner.runtime, -1.0, lower, upper,
                                  pelvis, roots, bases, headings, torch.zeros(1, dtype=torch.long))


def decoder(owner, args):
    if not hasattr(owner, 'surface_decoder'):
        eager = DecodeStep(owner).eval()
        fingerprint = hashlib.sha256((policy_graph_fingerprint()+inspect.getsource(decode_policy_rows)+inspect.getsource(DecodeStep)).encode()).hexdigest()
        path = ROOT/'.nn-cache'/('surface-decode-'+owner.gait+'.pt')
        tag = path.with_suffix('.sha256')
        graph = None
        if path.exists() and tag.exists() and tag.read_text() == fingerprint:
            graph = torch.jit.load(str(path)).eval()
        if graph is None:
            with torch.jit.optimized_execution(True), warnings.catch_warnings():
                warnings.simplefilter('ignore', torch.jit.TracerWarning)
                graph = torch.jit.freeze(torch.jit.trace(eager, args, check_trace=False))
            temporary = path.with_suffix('.tmp.pt')
            graph.save(str(temporary))
            temporary.replace(path)
            tag.write_text(fingerprint)
        for actual, expected in zip(graph(*args), eager(*args)):
            torch.testing.assert_close(actual, expected, rtol=1e-5, atol=3e-6)
        owner.surface_decoder = graph
    return owner.surface_decoder


class Stream:
    def __init__(self, owner, verify=False):
        self.owner = owner
        self.runtime = owner.runtime
        self.runtime.install_policy()
        self.mode = -1.0
        self.full = self.runtime.full_by_mode[self.mode]
        self.initialized = False
        self.ids = torch.zeros(1, dtype=torch.long)
        self.policy_seconds = 0.0
        self.verify = verify
        self.max_feature_error = 0.0

    def checkpoint(self):
        names = ('previous', 'current', 'prev_upper', 'cur_upper', 'prev_pelvis', 'cur_pelvis', 'base')
        return dict(initialized=self.initialized, policySeconds=self.policy_seconds,
                    tensors={name: getattr(self, name).tolist() for name in names} if self.initialized else {})

    def restore(self, state):
        self.initialized = bool(state['initialized'])
        self.policy_seconds = float(state.get('policySeconds', 0))
        if self.initialized:
            for name in ('previous', 'current', 'prev_upper', 'cur_upper', 'prev_pelvis', 'cur_pelvis', 'base'):
                value = torch.tensor(state['tensors'][name], dtype=torch.float32, device=self.owner.device)
                if value.ndim != 2 or value.shape[0] != 1 or not torch.isfinite(value).all():
                    raise ValueError('Invalid surface recurrent checkpoint')
                setattr(self, name, value)

    @inference_execution()
    def step(self, request):
        started = time.perf_counter()
        owner, runtime = self.owner, self.runtime
        store = runtime.store
        inverse = owner.course_axes.T
        roots = torch.tensor(request['roots'], dtype=torch.float32) @ inverse
        angles = torch.tensor(request['rootYawDegrees'], dtype=torch.float32)*math.pi/180
        _, basis, heading = runtime_data.root_state(runtime, self.ids)
        bases = basis @ tl.yaw_to_row_matrix(-angles)
        yaws = tl.heading_yaw_from_root(bases)
        headings = tl.yaw_to_row_matrix(yaws)
        pose_headings = heading @ tl.yaw_to_row_matrix(-angles)
        delta = (roots[1:2]-roots[0:1]) @ headings[0]
        first = torch.stack((delta[:, 0]/store.cfg.max_speed_scale_final,
                             delta[:, 2]/store.cfg.max_speed_scale_final,
                             tl.wrap_angle(yaws[1:2]-yaws[0:1])/store.cfg.max_turn_rate_scale_final), -1)
        future = int(store.cfg.future_window)
        steps = torch.arange(1, future+1)
        command = (roots[2:future+2]-roots[1]) @ headings[1]
        yaw_delta = tl.wrap_angle(yaws[2:future+2]-yaws[1])
        scale = steps*store.cfg.max_speed_scale_final
        window = torch.stack(((command[:, 0]/scale).clamp(-2, 2),
                              (command[:, 2]/scale).clamp(-2, 2),
                              torch.cos(yaw_delta), torch.sin(yaw_delta)), -1)
        features = torch.cat((first, window.reshape(1, -1)), -1)
        if self.verify:
            original = tl.root_state
            def root_state(clip, index, config, device):
                ix = (index+1).clamp(0, len(roots)-1)
                return roots[ix], bases[ix], yaws[ix], headings[ix]
            try:
                tl.root_state = root_state
                ix = torch.zeros(1, dtype=torch.long)
                expected = torch.cat((tl.root_delta_feature(runtime.lower_clip, ix-1, ix, store.cfg, owner.device),
                                      tl.future_root_features(runtime.lower_clip, ix, store.cfg, owner.device)), -1)
            finally:
                tl.root_state = original
            torch.testing.assert_close(features, expected, rtol=1e-5, atol=2e-6)
            self.max_feature_error = max(self.max_feature_error, float((features-expected).abs().max()))
        # The game rebases/decodes against the first root actually encoded in
        # the window (which has the native [-2,2] bounds), not the uncapped
        # physical forecast. Otherwise high fall speed tears the pose apart.
        next_root = roots[1:2]+torch.stack((window[0, 0]*store.cfg.max_speed_scale_final,
                                          roots[2, 1]-roots[1, 1],
                                          window[0, 1]*store.cfg.max_speed_scale_final))[None] @ headings[1].T
        if not self.initialized or request.get('reset'):
            if request['names'] != ['root', *self.full.body_names]:
                raise ValueError('Surface seed bone order differs')
            positions = torch.tensor([p['points'][1:] for p in request['seeds']], dtype=torch.float32) @ inverse
            rotations = torch.tensor([p['axes'][1:] for p in request['seeds']], dtype=torch.float32) @ inverse
            lower = encode_lower(runtime.lower_clip, positions, rotations, roots[:2], bases[:2])
            upper = upper_data.upper_state_from_global_pose_and_heading(self.full, positions, rotations, roots[:2], pose_headings[:2])
            self.previous, self.current = lower.split(1)
            self.prev_upper, self.cur_upper = upper.split(1)
            self.prev_pelvis = runtime_data.pelvis_heading_features(self.previous, bases[0:1], pose_headings[0:1])
            self.cur_pelvis = runtime_data.pelvis_heading_features(self.current, bases[1:2], pose_headings[1:2])
            self.base = runtime_data.base_upper_from_lower(self.current, roots[1:2], bases[1:2], pose_headings[1:2], self.full, runtime.rest_offsets_by_mode[self.mode][0:1])
            self.initialized = True
        args = (self.previous, self.current, self.prev_upper, self.cur_upper,
                self.prev_pelvis, self.base, roots[1:2], next_root, features,
                bases[1:2], pose_headings[1:2], bases[2:3], pose_headings[2:3])
        graph = compiled_step(owner, self.mode, basis, heading, args)
        following, next_upper, pelvis, next_base, pins = graph(*args)
        decode_args = (following, next_upper, pelvis, next_root, bases[2:3], pose_headings[2:3])
        p, r = decoder(owner, decode_args)(*decode_args)
        p, r = p @ owner.course_axes, r @ owner.course_axes
        if not torch.isfinite(p).all() or not torch.isfinite(r).all():
            raise ValueError('Surface NN became non-finite')
        self.previous, self.current = self.current, following
        self.prev_upper, self.cur_upper = self.cur_upper, next_upper
        self.prev_pelvis, self.cur_pelvis, self.base = self.cur_pelvis, pelvis, next_base
        self.policy_seconds += time.perf_counter()-started
        return dict(pose=dict(points=[(next_root @ owner.course_axes)[0].tolist(), *p[0].tolist()],
                              axes=[torch.eye(3).tolist(), *r[0].tolist()]),
                    pins=pins[0].tolist())


def run_surface(owner, request):
    started = time.perf_counter()
    version = hashlib.sha256(b''.join((ROOT/name).read_bytes() for name in FILES)).hexdigest()
    if request.get('sourceVersion') != version:
        raise ValueError('Surface solver changed during loading. Refresh Foot IK.')
    node = shutil.which('node')
    if node is None:
        raise ValueError('Node.js is required for the shared surface simulation')
    reference_error = None
    if request.get('verifyReference'):
        # A continuously retained stream must reproduce the existing recurrent
        # implementation, not merely produce finite looking poses.
        from directional_nn import resume_in_course
        source = request['source']
        count = 18
        reference_request = dict(gait=request['gait'], policy='run', direction=request['direction'],
                                 names=['root', *source['names']], frames=count, roots=source['roots'][:count+9],
                                 rootYawDegrees=source['rootYawDegrees'][:count+9], seeds=request['seeds'])
        expected = resume_in_course(owner, reference_request)
        probe = Stream(owner, True)
        reference_error = 0.0
        for i in range(count-1):
            step = dict(reference_request, roots=reference_request['roots'][i:i+12],
                        rootYawDegrees=reference_request['rootYawDegrees'][i:i+12])
            actual = probe.step(step)['pose']
            for key in ('points', 'axes'):
                a = torch.tensor(actual[key][1:]);b = torch.tensor(expected['poses'][i+1][key])
                reference_error = max(reference_error, float((a-b).abs().max()))
                torch.testing.assert_close(a, b, rtol=3e-5, atol=3e-5)
    stream = Stream(owner, request.get('verifyReference', False))
    child = subprocess.Popen([node, str(ROOT/'surface_driver.cjs')], cwd=ROOT,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, encoding='utf-8',
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        child.stdin.write(json.dumps(dict(source=request['source'], settings=request['settings']), separators=(',', ':'))+'\n')
        child.stdin.flush()
        for line in child.stdout:
            message = json.loads(line)
            if 'error' in message:
                raise ValueError(message['error'])
            if message.get('done'):
                child.stdin.close()
                child.wait(timeout=5)
                return dict(kind='surface', steps=message['steps'], diagnostics=message['diagnostics'],
                            seconds=time.perf_counter()-started, policySeconds=stream.policy_seconds,
                            referenceError=reference_error, featureError=stream.max_feature_error)
            result = stream.step(message['step'])
            child.stdin.write(json.dumps(result, separators=(',', ':'), allow_nan=False)+'\n')
            child.stdin.flush()
        raise ValueError('Surface physics peer stopped: '+child.stderr.read()[-1000:])
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        for pipe in (child.stdin, child.stdout, child.stderr):
            if not pipe.closed:
                pipe.close()


def source_version():
    return hashlib.sha256(b''.join((ROOT/name).read_bytes() for name in FILES)).hexdigest()


def session_identity(request):
    return hashlib.sha256(json.dumps({k: v for k, v in request.items() if k not in ('sessionId', 'endTime')},
                                    sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class SurfaceSession:
    """Retain the causal JS generator and exact NN state between trim extensions."""
    def __init__(self, owner, request, token=None, saved=None, peer=None):
        self.owner, self.request = owner, dict(request)
        self.token = token or uuid.uuid4().hex
        self.identity = session_identity(request)
        self.version = source_version()
        self.steps = list(saved['steps']) if saved else []
        self.stream = Stream(owner, request.get('verifyReference', False))
        self.generated = -1.0
        self.diagnostics = {}
        self.frame_batches = []
        self.read_index = 0
        node = shutil.which('node')
        if node is None:
            raise ValueError('Node.js is required for the shared surface simulation')
        if peer is not None:
            self.child, self.errors = peer.child, peer.errors
            peer.child, peer.errors = None, None
        else:
            self.errors = tempfile.TemporaryFile(mode='w+', encoding='utf-8')
            flags = (subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name == 'nt' else 0
            self.child = subprocess.Popen([node, str(ROOT/'surface_driver.cjs')], cwd=ROOT,
                                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.errors,
                                          text=True, encoding='utf-8', creationflags=flags)
        try:
            end = saved['generatedThrough'] if saved else request['endTime']
            initial = dict(source=request['source'], settings=request['settings'], endTime=end,
                           totalDuration=request.get('totalDuration', 5))
            self.send(dict(reset=initial) if peer is not None else initial)
            self.collect(replay=bool(saved))
            if saved:
                if self.read_index != len(self.steps):
                    raise ValueError('Saved surface prefix no longer reproduces its policy cadence')
                self.stream.restore(saved['state'])
        except Exception:
            self.close()
            raise

    def send(self, message):
        self.child.stdin.write(json.dumps(message, separators=(',', ':'), allow_nan=False)+'\n')
        self.child.stdin.flush()

    def collect(self, replay=False):
        for line in self.child.stdout:
            message = json.loads(line)
            if 'error' in message:
                raise ValueError(message['error'])
            if message.get('done'):
                batch = message.get('frameBatch')
                if not isinstance(batch, dict) or batch.get('start') != sum(b['count'] for b in self.frame_batches):
                    raise ValueError('Invalid surface pose prefix')
                self.frame_batches.append(batch)
                self.generated = float(message['generatedThrough'])
                self.diagnostics = message['diagnostics']
                return
            if 'step' not in message:
                raise ValueError('Unexpected surface session peer message')
            if self.read_index < len(self.steps):
                result = self.steps[self.read_index]
            elif replay:
                raise ValueError('Saved surface prefix requested an unrecorded policy step')
            else:
                result = self.stream.step(message['step'])
                self.steps.append(result)
            self.read_index += 1
            self.send(result)
        self.errors.seek(0)
        raise ValueError('Surface session peer stopped: '+self.errors.read()[-1000:])

    def extend(self, end_time):
        if end_time > self.generated+1e-9:
            self.send(dict(extend=end_time))
            self.collect()

    def saved(self):
        return dict(schema=1, version=self.version, identity=self.identity, request=self.request,
                    generatedThrough=self.generated, steps=self.steps, state=self.stream.checkpoint())

    def close(self):
        child = getattr(self, 'child', None)
        if child is not None:
            if not child.stdin.closed:
                child.stdin.close()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.terminate()
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            if not child.stdout.closed:
                child.stdout.close()
            self.child = None
        if getattr(self, 'errors', None) is not None and not self.errors.closed:
            self.errors.close()


class SurfaceSessions:
    """Two resident sessions; bounded disk receipts survive worker retirement."""
    def __init__(self):
        self.active = OrderedDict()
        self.folder = ROOT/'.nn-cache'
        self.folder.mkdir(exist_ok=True)

    def owner_for(self, request):
        item = self.active.get(request.get('sessionId'))
        return item.owner if item else None

    def close(self):
        for item in self.active.values():
            item.close()
        self.active.clear()

    def process(self, owner, request):
        started = time.perf_counter()
        version = source_version()
        if request.get('sourceVersion') != version:
            raise ValueError('Surface solver changed during loading. Refresh Foot IK.')
        end = float(request['endTime'])
        total = float(request.get('totalDuration', 5))
        if not math.isfinite(end) or not 0 <= end <= total <= 5:
            raise ValueError('Invalid bounded surface horizon')
        token = request.get('sessionId')
        if token is not None and (len(token) != 32 or any(c not in '0123456789abcdef' for c in token)):
            raise ValueError('Invalid surface session key')
        identity = session_identity(request)
        session = self.active.get(token)
        if session and (session.identity != identity or session.version != version):
            self.active.pop(token).close()
            session = None
            token = None
        old_count = len(session.steps) if session else 0
        restored = False
        saved = None
        if session is None and token:
            filename = self.folder/('surface-session-'+token+'.state.gz')
            if filename.exists():
                try:
                    candidate = json.loads(gzip.decompress(filename.read_bytes()))
                    if candidate.get('version') == version and candidate.get('identity') == identity:
                        saved = candidate
                        old_count = len(saved['steps'])
                        restored = True
                except (ValueError, OSError, KeyError):
                    pass
        if session is None:
            # Evict before allocating another physics peer or retained pose bank.
            peer = None
            while len(self.active) >= 2:
                _, expired = self.active.popitem(last=False)
                # Reset an idle same-version peer, retaining compiled JS only.
                # All pose/spring/NN state belongs to the new session or receipt.
                if expired.version == version and expired.child.poll() is None:
                    if peer is not None:
                        peer.close()
                    peer = expired
                else:
                    expired.close()
            session = SurfaceSession(owner, request, token=token, saved=saved, peer=peer)
            self.active[session.token] = session
        self.active.move_to_end(session.token)
        try:
            session.extend(end)
            record = session.saved()
            filename = self.folder/('surface-session-'+session.token+'.state.gz')
            temporary = filename.with_suffix('.tmp')
            temporary.write_bytes(gzip.compress(json.dumps(record, separators=(',', ':'), allow_nan=False).encode()))
            temporary.replace(filename)
            # Only our recomputable session records. Compiled graphs and ordinary
            # seed-response caches have separate ownership and remain untouched.
            for old in sorted(self.folder.glob('surface-session-*.state.gz'), key=lambda p: p.stat().st_mtime, reverse=True)[16:]:
                old.unlink()
            return dict(kind='surface', sessionId=session.token, generatedThrough=session.generated,
                        frameBatches=session.frame_batches, frameEncoding='gzip-json-v1',
                        stepStart=old_count, steps=session.steps, diagnostics=session.diagnostics,
                        appendedInferences=len(session.steps)-old_count, restored=restored,
                        seconds=time.perf_counter()-started, policySeconds=session.stream.policy_seconds,
                        referenceError=None, featureError=session.stream.max_feature_error)
        except Exception:
            self.active.pop(session.token, None)
            session.close()
            raise
