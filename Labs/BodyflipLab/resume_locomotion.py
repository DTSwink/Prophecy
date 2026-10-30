"""Seed the frozen lower/upper policies from a landing, using their original codecs.

Only used during preparation. One CPU thread; no training or CUDA execution.
Input axes are the same row matrices as locomotion.py's output, in metres/Y-up.
"""
import json
import math
import sys
import time
import hashlib
import warnings
from pathlib import Path
from locomotion import Locomotion, ROOT, torch, runtime_data, upper_ctl, upper_data, tl

lower_ctl = runtime_data.lower_ctl


class PolicyStep(torch.nn.Module):
    """Fixed single-agent policy step, traced from the original policy functions."""
    def __init__(self, owner, mode, basis, heading):
        super().__init__()
        self.lower = owner.runtime.model
        self.upper = owner.agent
        self.runtime, self.mode = owner.runtime, mode
        self.basis, self.heading = basis, heading

    def forward(self, previous, current, prev_upper, cur_upper, prev_pelvis, base, root, next_root, features):
        runtime, mode, basis, heading = self.runtime, self.mode, self.basis, self.heading
        store, full = runtime.store, runtime.full_by_mode[mode]
        payload = lower_ctl.payload_slice(store)
        inputs = torch.cat((current, previous,
            (current[:, :3]-previous[:, :3])/store.cfg.pose_delta_scale_final,
            (current[:, payload]-previous[:, payload])/store.cfg.pose_delta_scale_final, features), -1)
        raw = lower_ctl.model_raw_output(self.lower, inputs, current, store)
        transition = lower_ctl.clean_output_vector(raw, store, current, previous)
        following = (lower_ctl.rebase_output_vector_root(store, transition, root, basis, next_root, basis)
                     if tl.output_reference_uses_current_root() else lower_ctl.clean_output_vector(transition, store))
        pelvis = runtime_data.pelvis_heading_features(following, basis, heading)
        cur_pelvis = runtime_data.pelvis_heading_features(current, basis, heading)
        next_base = runtime_data.base_upper_from_lower(following, next_root, basis, heading, full, runtime.rest_offsets_by_mode[mode][0:1])
        prior = upper_data.clean_upper_state(next_base+cur_upper-base)
        feet = runtime_data.foot_heading_features(store, current, basis, heading)
        next_feet = runtime_data.foot_heading_features(store, following, basis, heading)
        inp = torch.cat((prev_upper, prior, prev_pelvis, cur_pelvis, pelvis, features,
                         torch.tensor([[mode]]), feet, next_feet, torch.zeros(1, 2)), -1)
        next_upper = upper_data.clean_upper_state(prior+self.upper(inp))
        geometry = runtime.full_geometry_by_mode[mode]
        next_upper = upper_ctl.clamp_viewer_forearm_lengths(full, next_upper, pelvis, geometry['local_offsets'][0:1], geometry['ik_limb_lengths'][0:1])
        return following, next_upper, pelvis, next_base


def compiled_step(owner, mode, basis, heading, example):
    if not hasattr(owner, 'steps'):
        owner.steps = {}
    if mode not in owner.steps:
        eager = PolicyStep(owner, mode, basis, heading).eval()
        folder = ROOT/'.resume-cache'
        folder.mkdir(exist_ok=True)
        path = folder/('step-'+owner.gait+'-'+str(int(mode))+'.pt')
        tag = path.with_suffix('.sha256')
        fingerprint = hashlib.sha256(Path(__file__).read_bytes()+(ROOT/'models/provenance.json').read_bytes()).hexdigest()
        if path.exists() and tag.exists() and tag.read_text() == fingerprint:
            traced = torch.jit.load(str(path)).eval()
        else:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', torch.jit.TracerWarning)
                traced = torch.jit.freeze(torch.jit.trace(eager, example, check_trace=False))
            traced.save(str(path))
            tag.write_text(fingerprint)
        # Never silently accept a compiled graph that changes the policy output.
        for actual, expected in zip(traced(*example), eager(*example)):
            torch.testing.assert_close(actual, expected, rtol=1e-5, atol=2e-6)
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
    @torch.inference_mode()
    def resume(self, request):
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
        if roots.ndim != 2 or roots.shape[1] != 3 or not 12 <= len(roots) <= 18100:
            raise ValueError('Invalid capsule root path')
        positions = torch.tensor([p['points'][1:] for p in poses], dtype=torch.float32)
        rotations = torch.tensor([p['axes'][1:] for p in poses], dtype=torch.float32)
        if positions.shape != (2, 25, 3) or rotations.shape != (2, 25, 3, 3):
            raise ValueError('Two complete landing history poses required')
        if not all(torch.isfinite(x).all() for x in (roots, positions, rotations)):
            raise ValueError('Non-finite landing state')
        # Shift large world coordinates together, never the body relative to root.
        continuation = request.get('continuation')
        origin = torch.tensor(continuation['origin'], dtype=torch.float32) if continuation else roots[1].clone()
        if origin.shape != (3,) or not torch.isfinite(origin).all():
            raise ValueError('Invalid continuation origin')
        roots = roots-origin
        positions = positions-origin
        ids = torch.zeros(1, dtype=torch.long)
        _, basis, heading = runtime_data.root_state(runtime, ids)
        count = int(request['frames'])
        future = int(store.cfg.future_window)
        if count < 2 or count+future+1 > len(roots):
            raise ValueError('Root path must include previous/current and future commands')

        def root_state(clip_ids, index):
            ix = (index+1).clamp(0, len(roots)-1)
            n = len(index)
            return roots[ix], basis.expand(n, -1, -1), torch.zeros(n), heading.expand(n, -1, -1)

        def root_features(clip_ids, index):
            current = roots[index+1]
            delta = (current-roots[index]) @ heading[0]
            first = torch.stack((delta[:, 0]/store.cfg.max_speed_scale_final,
                                 delta[:, 2]/store.cfg.max_speed_scale_final,
                                 torch.zeros(len(index))), -1)
            steps = torch.arange(1, future+1)
            command = (roots[index[:, None]+1+steps]-current[:, None]) @ heading[0]
            scale = steps*store.cfg.max_speed_scale_final
            window = torch.stack(((command[..., 0]/scale).clamp(-2, 2),
                                  (command[..., 2]/scale).clamp(-2, 2),
                                  torch.ones_like(command[..., 0]), torch.zeros_like(command[..., 0])), -1)
            return torch.cat((first, window.flatten(1)), -1)

        old_root, old_features = store.root_state, store.get_input_root_features
        store.root_state, store.get_input_root_features = root_state, root_features
        try:
            lower = encode_lower(runtime.lower_clip, positions, rotations, roots[:2], basis.expand(2, -1, -1))
            upper = upper_data.upper_state_from_global_pose_and_heading(full, positions, rotations, roots[:2], heading.expand(2, -1, -1))
            previous, current = lower.split(1)
            prev_upper, cur_upper = upper.split(1)
            prev_pelvis = runtime_data.pelvis_heading_features(previous, basis, heading)
            cur_pelvis = runtime_data.pelvis_heading_features(current, basis, heading)
            rest = runtime.rest_offsets_by_mode[mode][0:1]
            base = runtime_data.base_upper_from_lower(current, roots[1:2], basis, heading, full, rest)
            if continuation:
                # Preserve the recurrent policy state when extending a trimmed
                # preview. Re-encoding decoded bones loses internal history.
                for key in ('previous', 'current', 'prev_upper', 'cur_upper', 'prev_pelvis', 'cur_pelvis', 'base'):
                    if key not in continuation:
                        raise ValueError('Incomplete continuation state')
                expected = (previous, current, prev_upper, cur_upper, prev_pelvis, cur_pelvis, base)
                restored = [torch.tensor(continuation[key], dtype=torch.float32)
                    for key in ('previous', 'current', 'prev_upper', 'cur_upper', 'prev_pelvis', 'cur_pelvis', 'base')]
                if any(value.shape != template.shape for value, template in zip(restored, expected)):
                    raise ValueError('Invalid continuation state shape')
                previous, current, prev_upper, cur_upper, prev_pelvis, cur_pelvis, base = restored
                if not all(torch.isfinite(value).all() for value in (previous, current, prev_upper, cur_upper, prev_pelvis, cur_pelvis, base)):
                    raise ValueError('Non-finite continuation state')
            # First visible frame is EXACTLY the supplied landing pose. Subsequent
            # frames are recurrent inference, not a fade into an unrelated gait.
            rows = [dict(points=poses[1]['points'][1:], axes=poses[1]['axes'][1:])]
            lower_rows, upper_rows, pelvis_rows = [], [], []
            step = compiled_step(self, mode, basis, heading,
                (previous, current, prev_upper, cur_upper, prev_pelvis, base, roots[1:2], roots[2:3], root_features(ids, torch.tensor([0]))))
            reference_error = 0.0
            reference_step = PolicyStep(self, mode, basis, heading).eval() if request.get('verifyReference') else None
            for k in range(count-1):
                index = torch.tensor([k])
                features = root_features(ids, index)
                following, next_upper, pelvis, next_base = step(previous, current, prev_upper, cur_upper,
                    prev_pelvis, base, roots[k+1:k+2], roots[k+2:k+3], features)
                if reference_step is not None:
                    reference = reference_step(previous, current, prev_upper, cur_upper, prev_pelvis, base, roots[k+1:k+2], roots[k+2:k+3], features)
                    for actual, expected in zip((following, next_upper, pelvis, next_base), reference):
                        reference_error = max(reference_error, float((actual-expected).abs().max()))
                        torch.testing.assert_close(actual, expected, rtol=1e-5, atol=2e-6)
                    original_input = lower_ctl.build_controller_input(store, ids, index, previous, current,
                        previous[:, :3], current[:, :3], previous[:, lower_ctl.payload_slice(store)], current[:, lower_ctl.payload_slice(store)])
                    raw_reference = lower_ctl.model_raw_output(runtime.model, original_input, current, store)
                    transition_reference = lower_ctl.clean_output_vector(raw_reference, store, current, previous)
                    original_lower = lower_ctl.advance_transition_state(store, ids, index, transition_reference)[0]
                    torch.testing.assert_close(following, original_lower, rtol=1e-5, atol=2e-6)
                lower_rows.append(following)
                upper_rows.append(next_upper)
                pelvis_rows.append(pelvis)
                previous, current = current, following
                prev_upper, cur_upper = cur_upper, next_upper
                prev_pelvis, cur_pelvis, base = cur_pelvis, pelvis, next_base
            # Decoding is independent across policy frames; batch it once rather
            # than repeating the skeleton traversal hundreds of times.
            n = count-1
            p, r = upper_ctl.decode_rows(runtime, mode, torch.cat(lower_rows), torch.cat(upper_rows),
                torch.cat(pelvis_rows), roots[2:count+1], basis.expand(n, -1, -1), heading.expand(n, -1, -1), ids.expand(n))
            if not torch.isfinite(p).all() or not torch.isfinite(r).all():
                raise ValueError('Landing NN continuation became non-finite')
            rows.extend(dict(points=a, axes=b) for a, b in zip((p+origin).tolist(), r.tolist()))
            return dict(names=list(full.body_names), fps=30, duration=(count-1)/30, poses=rows,
                        roots=(roots[1:count+1]+origin).tolist(), source='landing-seeded lower + upper NN',
                        seedLower=lower.tolist(), seedUpper=upper.tolist(), inferences=count-1,
                        continuation=dict(origin=origin.tolist(), previous=previous.tolist(), current=current.tolist(),
                            prev_upper=prev_upper.tolist(), cur_upper=cur_upper.tolist(),
                            prev_pelvis=prev_pelvis.tolist(), cur_pelvis=cur_pelvis.tolist(), base=base.tolist()),
                        referenceError=reference_error if reference_step is not None else None, seconds=time.perf_counter()-started)
        finally:
            store.root_state, store.get_input_root_features = old_root, old_features


if __name__ == '__main__':
    # Parent owns lifetime and serializes requests. Retain only the last gait.
    model = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            gait = request['gait']
            if model is None or model.gait != gait:
                model = ResumeLocomotion(gait)
            result = model.resume(request)
            print(json.dumps(result, separators=(',', ':'), allow_nan=False), flush=True)
        except Exception as error:
            print(json.dumps({'error': str(error)}), flush=True)
