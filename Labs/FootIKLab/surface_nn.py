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

from locomotion import torch, runtime_data, upper_data, tl
from directional_nn import decode_policy_rows
from nn_worker import encode_lower, compiled_step, inference_execution, policy_graph_fingerprint

ROOT = Path(__file__).resolve().parent
FILES = ('surface.js', 'surface-coupling.js', 'surface_driver.cjs', 'surface_nn.py',
         'footik.js', 'support.js', 'recovery.js')


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
        if not self.initialized:
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
