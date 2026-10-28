"""Seed the frozen lower/upper policies from a landing, using their original codecs.

Only used during preparation. One CPU thread; no training or CUDA execution.
Adapted from Bodyflip resume_locomotion.py; no changes to that lab.
Input axes are the same row matrices as locomotion.py's output, in metres/Y-up.
"""
import json
import math
import sys
import time
import hashlib
import inspect
import warnings
from contextlib import contextmanager
from pathlib import Path
# Reuse the frozen codec/model loader read-only; worker/cache ownership stays here.
sys.dont_write_bytecode = True
MODEL_ROOT = Path(__file__).resolve().parent.parent/'BodyflipLab'
sys.path.insert(0, str(MODEL_ROOT))
from locomotion import Locomotion, torch, runtime_data, upper_ctl, upper_data, tl
ROOT = Path(__file__).resolve().parent

from directional_nn import decode_policy_rows

lower_ctl = runtime_data.lower_ctl


@contextmanager
def inference_execution():
    # Frozen graphs already contain the inference optimizations. Reprofiling
    # them on every short-lived worker adds startup cost without faster steps.
    with torch.inference_mode(), torch.jit.optimized_execution(False):
        yield


class PolicyStep(torch.nn.Module):
    """Fixed single-agent policy step, traced from the original policy functions."""
    def __init__(self, owner, mode, basis, heading):
        super().__init__()
        self.lower = owner.runtime.model
        self.upper = owner.agent
        self.runtime, self.mode = owner.runtime, mode
        self.basis, self.heading = basis, heading

    def forward(self, previous, current, prev_upper, cur_upper, prev_pelvis, base, root, next_root, features,
                basis, heading, next_basis, next_heading):
        runtime, mode = self.runtime, self.mode
        store, full = runtime.store, runtime.full_by_mode[mode]
        payload = lower_ctl.payload_slice(store)
        inputs = torch.cat((current, previous,
            (current[:, :3]-previous[:, :3])/store.cfg.pose_delta_scale_final,
            (current[:, payload]-previous[:, payload])/store.cfg.pose_delta_scale_final, features), -1)
        raw = lower_ctl.model_raw_output(self.lower, inputs, current, store)
        transition, _, pin_probability = lower_ctl.clean_output_vector_pair_with_pin_prob(raw, store, current, previous)
        following = (lower_ctl.rebase_output_vector_root(store, transition, root, basis, next_root, next_basis)
                     if tl.output_reference_uses_current_root() else lower_ctl.clean_output_vector(transition, store))
        pelvis = runtime_data.pelvis_heading_features(following, next_basis, next_heading)
        cur_pelvis = runtime_data.pelvis_heading_features(current, basis, heading)
        next_base = runtime_data.base_upper_from_lower(following, next_root, next_basis, next_heading, full, runtime.rest_offsets_by_mode[mode][0:1])
        prior = upper_data.clean_upper_state(next_base+cur_upper-base)
        feet = runtime_data.foot_heading_features(store, current, basis, heading)
        next_feet = runtime_data.foot_heading_features(store, following, next_basis, next_heading)
        inp = torch.cat((prev_upper, prior, prev_pelvis, cur_pelvis, pelvis, features,
                         torch.tensor([[mode]]), feet, next_feet, torch.zeros(1, 2)), -1)
        next_upper = upper_data.clean_upper_state(prior+self.upper(inp))
        geometry = runtime.full_geometry_by_mode[mode]
        next_upper = upper_ctl.clamp_viewer_forearm_lengths(full, next_upper, pelvis, geometry['local_offsets'][0:1], geometry['ik_limb_lengths'][0:1])
        return following, next_upper, pelvis, next_base, pin_probability


def policy_graph_fingerprint():
    """Only invalidate a traced policy when its graph or dependencies change.

    Resume orchestration/diagnostics do not participate in this graph. Hashing
    the entire worker made every such edit retrace the same frozen network.
    """
    digest = hashlib.sha256(b'footik-policy-graph-v1')
    digest.update(inspect.getsource(PolicyStep).encode('utf-8'))
    digest.update(torch.__version__.encode('utf-8'))
    for path in [(MODEL_ROOT/'locomotion.py'), (MODEL_ROOT/'models/provenance.json'),
                 *[Path(module.__file__) for module in (runtime_data, upper_ctl, upper_data, tl, lower_ctl)]]:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def compiled_step(owner, mode, basis, heading, example):
    if not hasattr(owner, 'steps'):
        owner.steps = {}
    if mode not in owner.steps:
        eager = PolicyStep(owner, mode, basis, heading).eval()
        folder = ROOT/'.nn-cache'
        folder.mkdir(exist_ok=True)
        path = folder/('step-'+owner.gait+'-'+str(int(mode))+'.pt')
        tag = path.with_suffix('.sha256')
        fingerprint = policy_graph_fingerprint()
        def validate_graph(graph):
            # Never silently accept a graph that changes the policy output.
            for actual, expected in zip(graph(*example), eager(*example)):
                torch.testing.assert_close(actual, expected, rtol=1e-5, atol=2e-6)
        traced = None
        if path.exists() and tag.exists() and tag.read_text() == fingerprint:
            try:
                traced = torch.jit.load(str(path)).eval()
                validate_graph(traced)
            except (RuntimeError, OSError, AssertionError):
                traced = None  # Interrupted/invalid disposable graph; rebuild.
        if traced is None:
            # Execution can skip profiling, but tracing/freezing must inline
            # submodule calls before their methods are removed by freezing.
            with torch.jit.optimized_execution(True), warnings.catch_warnings():
                warnings.simplefilter('ignore', torch.jit.TracerWarning)
                traced = torch.jit.freeze(torch.jit.trace(eager, example, check_trace=False))
            validate_graph(traced)
            temporary = path.with_suffix('.tmp.pt')
            traced.save(str(temporary))
            temporary.replace(path)
            tag.write_text(fingerprint)
        owner.steps[mode] = traced
    return owner.steps[mode]


def encode_lower(clip, positions, rotations, root_position, root_rotation):
    """Same pelvis, ankle, thigh and toe channels as Unreal's pose feedback."""
    inverse = root_rotation.transpose(-1, -2)
    local_p = (positions - root_position[:, None]) @ inverse
    local_r = rotations @ inverse[:, None]
    parts = [local_p[:, 0], tl.rotmat_to_6d(local_r[:, 0])]
    for limb, spec in enumerate(clip.ik_limb_specs):
        foot, thigh, toe = int(spec['end']), int(spec['start']), int(spec['toe'])
        parts.extend((local_p[:, foot], tl.rotmat_to_6d(local_r[:, foot]),
                      tl.rotmat_to_6d(local_r[:, thigh])))
        axis = clip.ik_toe_axis[limb:limb+1]
        ref = tl.stable_perpendicular(axis)
        relative = rotations[:, toe] @ rotations[:, foot].transpose(-1, -2)
        rotated = tl.project_to_plane((ref[:, None] @ relative).squeeze(1), axis)
        angle = torch.atan2((torch.cross(ref, rotated, dim=-1)*axis).sum(-1), (ref*rotated).sum(-1))
        parts.append((angle/tl.IK_TOE_ALPHA).clamp(-1, 1)[:, None])
    # Do not project/clamp the landing to a different leg pose before inference.
    return torch.cat(parts, -1)


class ResumeLocomotion(Locomotion):
    @inference_execution()
    def resume(self, request, max_frames=152):
        started = time.perf_counter()
        runtime = self.runtime
        runtime.install_policy()
        store = runtime.store
        mode = 1.0 if request.get('drawn') else -1.0
        full = runtime.full_by_mode[mode]
        if request['names'] != ['root', *full.body_names]:
            raise ValueError('Landing bone order differs from the frozen policy')
        roots = torch.tensor(request['roots'], dtype=torch.float32)
        poses = request['seeds']
        if roots.ndim != 2 or roots.shape[1] != 3 or not 12 <= len(roots) <= max_frames+48:
            raise ValueError('Invalid capsule root path')
        positions = torch.tensor([p['points'][1:] for p in poses], dtype=torch.float32)
        rotations = torch.tensor([p['axes'][1:] for p in poses], dtype=torch.float32)
        if positions.shape != (2, 25, 3) or rotations.shape != (2, 25, 3, 3):
            raise ValueError('Two complete landing history poses required')
        if not all(torch.isfinite(x).all() for x in (roots, positions, rotations)):
            raise ValueError('Non-finite landing state')
        # Shift large world coordinates together, never the body relative to root.
        origin = roots[1].clone()
        roots = roots-origin
        positions = positions-origin
        ids = torch.zeros(1, dtype=torch.long)
        _, basis, heading = runtime_data.root_state(runtime, ids)
        angles = torch.tensor(request.get('rootYawDegrees', [0.0]*len(roots)), dtype=torch.float32)*math.pi/180
        if angles.shape != (len(roots),) or not torch.isfinite(angles).all():
            raise ValueError('One finite yaw command per previous/current/future root required')
        bases = basis @ tl.yaw_to_row_matrix(-angles)
        yaws = tl.heading_yaw_from_root(bases)
        headings = tl.yaw_to_row_matrix(yaws)
        # Root-window features use world-to-heading matrices. Upper pose codecs
        # transpose their heading argument, so they need the pose frame carried
        # WITH the root, not that inverse. Reusing `headings` doubled world yaw
        # in pelvis/feet/hand inputs and made the upper policy change with world
        # orientation. Match Unreal's LowerTransformToHeading: the bridge from
        # lower root-local coordinates into upper coordinates stays constant.
        pose_headings = heading @ tl.yaw_to_row_matrix(-angles)
        count = int(request['frames'])
        future = int(store.cfg.future_window)
        if count < 2 or count > max_frames or count+future+1 > len(roots):
            raise ValueError('Root path must include previous/current and future commands')

        def root_state(clip_ids, index):
            ix = (index+1).clamp(0, len(roots)-1)
            return roots[ix], bases[ix], yaws[ix], headings[ix]

        def root_features(clip_ids, index):
            current = roots[index+1]
            delta = ((current-roots[index])[:, None] @ headings[index]).squeeze(1)
            first = torch.stack((delta[:, 0]/store.cfg.max_speed_scale_final,
                                 delta[:, 2]/store.cfg.max_speed_scale_final,
                                 tl.wrap_angle(yaws[index+1]-yaws[index])/store.cfg.max_turn_rate_scale_final), -1)
            steps = torch.arange(1, future+1)
            command = (roots[index[:, None]+1+steps]-current[:, None]) @ headings[index+1]
            yaw_delta = tl.wrap_angle(yaws[index[:, None]+1+steps]-yaws[index+1, None])
            scale = steps*store.cfg.max_speed_scale_final
            window = torch.stack(((command[..., 0]/scale).clamp(-2, 2),
                                  (command[..., 2]/scale).clamp(-2, 2),
                                  torch.cos(yaw_delta), torch.sin(yaw_delta)), -1)
            return torch.cat((first, window.flatten(1)), -1)

        old_root, old_features = store.root_state, store.get_input_root_features
        store.root_state, store.get_input_root_features = root_state, root_features
        try:
            lower = encode_lower(runtime.lower_clip, positions, rotations, roots[:2], bases[:2])
            upper = upper_data.upper_state_from_global_pose_and_heading(full, positions, rotations, roots[:2], pose_headings[:2])
            previous, current = lower.split(1)
            prev_upper, cur_upper = upper.split(1)
            prev_pelvis = runtime_data.pelvis_heading_features(previous, bases[0:1], pose_headings[0:1])
            cur_pelvis = runtime_data.pelvis_heading_features(current, bases[1:2], pose_headings[1:2])
            rest = runtime.rest_offsets_by_mode[mode][0:1]
            base = runtime_data.base_upper_from_lower(current, roots[1:2], bases[1:2], pose_headings[1:2], full, rest)
            # First visible frame is EXACTLY the supplied landing pose. Subsequent
            # frames are recurrent inference, not a fade into an unrelated gait.
            rows = [dict(points=poses[1]['points'][1:], axes=poses[1]['axes'][1:])]
            lower_rows, upper_rows, pelvis_rows, pin_rows = [], [], [], []
            step = compiled_step(self, mode, basis, heading,
                (previous, current, prev_upper, cur_upper, prev_pelvis, base, roots[1:2], roots[2:3], root_features(ids, torch.tensor([0])), bases[1:2], pose_headings[1:2], bases[2:3], pose_headings[2:3]))
            reference_error = 0.0
            window_error, projection_change, pin_max = 0.0, 0.0, 0.0
            reference_step = PolicyStep(self, mode, basis, heading).eval() if request.get('verifyReference') else None
            for k in range(count-1):
                index = torch.tensor([k])
                features = root_features(ids, index)
                following, next_upper, pelvis, next_base, pin_probability = step(previous, current, prev_upper, cur_upper,
                    prev_pelvis, base, roots[k+1:k+2], roots[k+2:k+3], features, bases[k+1:k+2], pose_headings[k+1:k+2], bases[k+2:k+3], pose_headings[k+2:k+3])
                if reference_step is not None:
                    # Compare with the ORIGINAL training encoder, not another
                    # copy of our vectorized feature implementation.
                    original_root_state = tl.root_state
                    try:
                        tl.root_state = lambda clip, ix, cfg, device: root_state(ids.expand(len(ix)), ix)
                        expected_features = torch.cat((tl.root_delta_feature(runtime.lower_clip, index-1, index, store.cfg, self.device),
                            tl.future_root_features(runtime.lower_clip, index, store.cfg, self.device)), -1)
                    finally:
                        tl.root_state = original_root_state
                    torch.testing.assert_close(features, expected_features, rtol=1e-5, atol=2e-6)
                    window_error = max(window_error, float((features-expected_features).abs().max()))
                    reference = reference_step(previous, current, prev_upper, cur_upper, prev_pelvis, base, roots[k+1:k+2], roots[k+2:k+3], features, bases[k+1:k+2], pose_headings[k+1:k+2], bases[k+2:k+3], pose_headings[k+2:k+3])
                    for actual, expected in zip((following, next_upper, pelvis, next_base, pin_probability), reference):
                        reference_error = max(reference_error, float((actual-expected).abs().max()))
                        torch.testing.assert_close(actual, expected, rtol=1e-5, atol=2e-6)
                    original_input = lower_ctl.build_controller_input(store, ids, index, previous, current,
                        previous[:, :3], current[:, :3], previous[:, lower_ctl.payload_slice(store)], current[:, lower_ctl.payload_slice(store)])
                    raw_reference = lower_ctl.model_raw_output(runtime.model, original_input, current, store)
                    transition_reference = lower_ctl.clean_output_vector(raw_reference, store, current, previous)
                    projected, unprojected, probabilities = lower_ctl.clean_output_vector_pair_with_pin_prob(raw_reference, store, current, previous)
                    projection_change = max(projection_change, float((projected-unprojected).abs().max()))
                    pin_max = max(pin_max, float(probabilities.max()))
                    original_lower = lower_ctl.advance_transition_state(store, ids, index, transition_reference)[0]
                    torch.testing.assert_close(following, original_lower, rtol=1e-5, atol=2e-6)
                pin_rows.append(pin_probability)
                lower_rows.append(following)
                upper_rows.append(next_upper)
                pelvis_rows.append(pelvis)
                previous, current = current, following
                prev_upper, cur_upper = cur_upper, next_upper
                prev_pelvis, cur_pelvis, base = cur_pelvis, pelvis, next_base
            # Decoding is independent across policy frames; batch it once rather
            # than repeating the skeleton traversal hundreds of times.
            n = count-1
            p, r = decode_policy_rows(self, runtime, mode, torch.cat(lower_rows), torch.cat(upper_rows),
                torch.cat(pelvis_rows), roots[2:count+1], bases[2:count+1], pose_headings[2:count+1], ids.expand(n))
            if not torch.isfinite(p).all() or not torch.isfinite(r).all():
                raise ValueError('Landing NN continuation became non-finite')
            rows.extend(dict(points=a, axes=b) for a, b in zip((p+origin).tolist(), r.tolist()))
            return dict(names=list(full.body_names), fps=30, duration=(count-1)/30, poses=rows,
                        roots=(roots[1:count+1]+origin).tolist(), source='terrain-seeded lower + upper NN',
                        seedLower=lower.tolist(), seedUpper=upper.tolist(), inferences=count-1,
                        pins=[None, *torch.cat(pin_rows).tolist()],
                        rootYawDegrees=(angles[1:count+1]*180/math.pi).tolist(), nnRootWindow=True,
                        rootFeatures=root_features(ids.expand(count-1), torch.arange(count-1)).tolist() if request.get('verifyReference') else None,
                        windowReferenceError=window_error if reference_step is not None else None,
                        pinDiagnostics=dict(mode=lower_ctl.FOOT_ROLL_PIN_MODE, maximum=pin_max, projectionChange=projection_change) if reference_step is not None else None,
                        referenceError=reference_error if reference_step is not None else None, seconds=time.perf_counter()-started)
        finally:
            store.root_state, store.get_input_root_features = old_root, old_features


if __name__ == '__main__':
    # Parent owns lifetime and serializes requests. Retain only the last gait.
    from directional_nn import configure_direction, generate, generate_command, resume_in_course
    model, model_key = None, None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            gait = 'run' if request.get('policy') == 'run' else request['gait']
            direction = request.get('direction', 'forward')
            key = (gait, direction)
            if model_key != key:
                model = ResumeLocomotion(gait)
                if direction != 'forward' or request.get('kind') in ('direction', 'surface'):
                    configure_direction(model, gait, direction)
                model_key = key
            if request.get('kind') == 'direction':
                if not hasattr(model, 'policy_gait'):
                    configure_direction(model, gait, direction)
                result = generate_command(model, request) if request.get('policy') == 'run' else generate(model, request)
            elif request.get('kind') == 'surface':
                if not hasattr(model, 'policy_gait'):
                    configure_direction(model, gait, direction)
                import importlib
                import surface_nn
                result = importlib.reload(surface_nn).run_surface(model, request)
            else:
                result = resume_in_course(model, request) if hasattr(model, 'course_axes') else model.resume(request)
            print(json.dumps(result, separators=(',', ':'), allow_nan=False), flush=True)
        except Exception as error:
            print(json.dumps({'error': str(error)}), flush=True)
