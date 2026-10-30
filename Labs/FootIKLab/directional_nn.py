"""Frozen omni NN rolls, initialized from the matching directional source.

The only authoring data used is the original policy's matched initial history
and root command. Every visible joint pose is recurrent lower + upper inference.
The whole generated motion is then rigidly aligned to the lab's +Z course; the
body is NOT made to face the travel direction. One CPU thread, bounded 5s rolls.

Worker integration: configure_direction(ResumeLocomotion(gait), gait, direction)
then generate(owner, request). For continuation use owner's existing resume()
after undoing result['sourceToCourseAxes'] on the supplied history/root path.
"""
import hashlib
import inspect
import json
import math
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
MODEL_ROOT = ROOT.parent / 'BodyflipLab'
sys.path.insert(0, str(MODEL_ROOT))
from locomotion import Locomotion, torch, runtime_data, upper_ctl, upper_data, tl
from locomotion import cached_data

# LR/RL are the accepted lateral clips (LL/RR were removed from the gallery).
SUFFIX = {'forward': 'F', 'backward': 'B', 'left': 'LR', 'right': 'RL'}
# Original Unreal NN gallery's measured full-stride cuts, in 60Hz game frames.
STRIDE_TICKS = {'walk': {'forward': 57, 'backward': 60, 'left': 59, 'right': 61},
                'run': {'forward': 38, 'backward': 39, 'left': 35, 'right': 36}}


def yaw_distance_options(request):
    start = float(request.get('rootYawStart', 0))
    stop = request.get('rootYawStop')
    stop = None if stop is None or stop == '' else float(stop)
    if not math.isfinite(start) or start < 0 or (stop is not None and (not math.isfinite(stop) or stop < start)):
        raise ValueError('Yaw distances require 0 <= start <= stop; blank stop is unlimited')
    return start, stop


def yaw_command(time, speed, omega, start=0, stop=None):
    """Integrate angular velocity only inside the root's travel-distance span.

    The course command is constant-speed +Z. Keep its stopped yaw rather than
    snapping back to the initial heading, including future window samples.
    """
    distance = max(0., speed*time)
    if stop is not None:
        distance = min(distance, stop)
    return omega*max(0., distance-start)/speed if speed > 1e-8 else 0.


def validate(request):
    gait, direction = request.get('gait', 'walk'), request.get('direction', 'forward')
    duration, phase = float(request.get('duration', 5)), float(request.get('phase', 0))
    if gait not in STRIDE_TICKS or direction not in SUFFIX:
        raise ValueError('Expected Walk/Run and forward/backward/left/right')
    if not math.isfinite(duration) or not .1 <= duration <= 5:
        raise ValueError('Directional duration must be .1-5 seconds')
    if not math.isfinite(phase) or not 0 <= phase <= 1:
        raise ValueError('Directional phase must be 0-1')
    return gait, direction, duration, phase


def configure_direction(owner, gait, direction):
    """Reuse one already loaded frozen model pair; replace only source context."""
    validate(dict(gait=gait, direction=direction))
    relative = f'{gait}_omni/M_Neutral_{gait.title()}_Loop_{SUFFIX[direction]}.npz'
    source = runtime_data.ORIGINAL_ROOT / relative
    drawn = runtime_data.DRAWN_ROOT / relative
    if not source.is_file() or not drawn.is_file():
        raise FileNotFoundError('Missing matched immutable directional source: ' + relative)
    original = owner.runtime
    owner.runtime = runtime_data.CategoryRuntime(gait, original.checkpoint, original.cfg,
        original.model, [relative], owner.device, lower_source_paths=[source],
        full_source_paths_by_mode={-1.0: [source], 1.0: [drawn]}, cyclic_flags=[True])
    owner.policy_gait, owner.direction = gait, direction
    # ResumeLocomotion's compiled step includes fixed skeleton context. Give each
    # context a distinct cache name so no forward graph can decode a side seed.
    owner.cache, owner.cache_limit, owner.calls, owner.steps = None, 0, 0, {}
    owner.command_seeds = {}
    manifest = json.loads((ROOT/'directional-sources.json').read_text(encoding='utf-8'))
    contract = manifest['sources'][gait][direction]
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (source, drawn)]
    if hashes != [contract['source']['sha256'], contract['drawn']['sha256']]:
        raise RuntimeError('Immutable directional seed changed: ' + relative)
    owner.direction_sources = dict(relative=relative, sourceSha256=hashes[0], drawnSha256=hashes[1])
    owner.gait = gait + '-' + direction + '-' + owner.direction_sources['sourceSha256'][:12]
    store = owner.runtime.store
    p, r, _ = runtime_data.root_state(owner.runtime, torch.tensor([0, 1]))
    velocity = (p[1] - p[0]) * 30
    source_speed = float(torch.linalg.vector_norm(velocity[[0, 2]]))
    # LR/RL native captures use their authored 350cm/s. The historical 345cm/s
    # cap belongs to RR_offset's different movement angle, which is not used.
    command_speed = source_speed
    angle = math.atan2(float(velocity[0]), float(velocity[2]))
    c, s = math.cos(angle), math.sin(angle)
    owner.course_axes = torch.tensor([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=torch.float32)
    forward = -r[0, 1] @ owner.course_axes
    owner.direction_info = dict(direction=direction, sourceSpeed=source_speed,
        commandSpeed=command_speed, sourceToCourseAxes=owner.course_axes.tolist(),
        facingDegrees=math.degrees(math.atan2(float(forward[0]), float(forward[2]))),
        policyGait=gait, **owner.direction_sources)
    return owner


@torch.inference_mode()
def decode_policy_rows(owner, runtime, mode, lower, upper, pelvis, roots, bases, headings, ids):
    """Overlay the upper policy without re-solving the lower policy's knees.

    The pelvis-controller decoder runs a second two-bone solve even when
    the pelvis is unchanged. Locomotion predicts thigh rotation directly;
    its native/model-viewer decoder derives the knee from that rotation.
    Use the original composed payload and FK, retaining those predictions.
    """
    full = runtime.full_by_mode[mode]
    vector = upper_ctl.contract._compose_full_vector(
        full, runtime.lower_clip, lower, upper, pelvis, bases, headings)
    pose, _ = tl.output_to_pose(vector, full)
    positions, rotations, _ = tl.fk_from_pose(full, roots, bases, pose, owner.device)
    # The full-body source can carry different measured pole axes/lengths.
    # Lower joints must use the lower checkpoint's own geometry, too.
    lower_pose, _ = tl.output_to_pose(lower, runtime.lower_clip)
    lower_p, lower_r, _ = tl.fk_from_pose(runtime.lower_clip, roots, bases, lower_pose, owner.device)
    indices = [runtime.lower_clip.pelvis]
    for limb in runtime.lower_clip.ik_limb_specs:
        indices.extend(int(limb[key]) for key in ('start', 'mid', 'end', 'toe'))
    for index in indices:
        target = full.body_names.index(runtime.lower_clip.body_names[index])
        positions[:, target], rotations[:, target] = lower_p[:, index], lower_r[:, index]
    return positions, rotations


@torch.inference_mode()
def generate(owner, request):
    gait, direction, duration, phase = validate(request)
    if owner.policy_gait != gait or owner.direction != direction:
        raise ValueError('Directional worker context differs from the request')
    started = time.perf_counter()
    runtime, mode = owner.runtime, 1.0 if request.get('drawn') else -1.0
    runtime.install_policy()
    full, ids = runtime.full_by_mode[mode], torch.zeros(1, dtype=torch.long)
    stride = STRIDE_TICKS[gait][direction] / 2
    start = 60 + round((phase % 1) * stride)
    warm = max(2, start - math.ceil(stride))
    count = math.ceil(duration * 30) + 2
    if owner.cache is None or getattr(owner, 'cache_limit', 0) < start+count:
        owner.cache_limit = max(90, start+count+2)
        payload = cached_data.build_category_cache(runtime, owner.lower_path, maximum_k=owner.cache_limit)
        owner.cache = cached_data.CachedLowerCategory(payload, runtime, owner.lower_path, owner.device)
    cache, gaze = owner.cache, torch.zeros((1, 2))
    def gather(name, index):
        return cache.gather(name, ids, torch.tensor([index]))
    def base(index):
        return cache.base_upper(mode, ids, torch.tensor([index]))
    seeds = runtime_data.upper_overlay_runtime_rows(runtime, mode, ids.repeat(2),
        torch.tensor([warm-1, warm]), gaze.repeat(2, 1), owner.device)
    previous, current = seeds.split(1)
    offsets = runtime.full_geometry_by_mode[mode]['local_offsets'][0:1]
    lengths = runtime.full_geometry_by_mode[mode]['ik_limb_lengths'][0:1]
    uppers, lower_rows, pelvis_rows, roots, bases, headings = [], [], [], [], [], []
    max_reference_error, reference_count = 0.0, 0
    for index in range(warm, start+count):
        if index > warm:
            k = index-1
            prior = upper_data.clean_upper_state(base(index)+current-base(k))
            inputs = torch.cat((previous, prior, gather('pelvis_heading', k-1),
                gather('pelvis_heading', k), gather('pelvis_heading', index),
                gather('root_features', k), torch.full((1, 1), mode),
                gather('feet_heading', k), gather('feet_heading', index), gaze), -1)
            following = upper_data.clean_upper_state(prior+owner.agent(inputs))
            following = upper_ctl.clamp_viewer_forearm_lengths(full, following,
                gather('pelvis_heading', index), offsets, lengths)
            previous, current = current, following
        if index < start:
            continue
        lower = gather('lower_vector', index)
        # Independently recompute the exact original lower controller input and
        # transition for selected samples rather than only checking finiteness.
        if request.get('verifyReference') and index in (start, start+count//2, start+count-1):
            lc, store, k = runtime_data.lower_ctl, runtime.store, index-1
            old, cur = gather('lower_vector', k-1), gather('lower_vector', k)
            payload = lc.payload_slice(store)
            inp = lc.build_controller_input(store, ids, torch.tensor([k]), old, cur,
                old[:, :3], cur[:, :3], old[:, payload], cur[:, payload])
            raw = lc.model_raw_output(runtime.model, inp, cur, store)
            nxt = lc.advance_transition_state(store, ids, torch.tensor([k]),
                lc.clean_output_vector(raw, store, cur, old))[0]
            torch.testing.assert_close(lower, nxt, rtol=1e-5, atol=2e-6)
            max_reference_error = max(max_reference_error, float((lower-nxt).abs().max()))
            reference_count += 1
        lower_rows.append(lower)
        uppers.append(current)
        pelvis_rows.append(gather('pelvis_heading', index))
        roots.append(gather('root_position', index))
        bases.append(gather('root_rotation', index))
        headings.append(gather('heading', index))
    p, r = decode_policy_rows(owner, runtime, mode, torch.cat(lower_rows), torch.cat(uppers),
        torch.cat(pelvis_rows), torch.cat(roots), torch.cat(bases), torch.cat(headings), ids.expand(count))
    roots = torch.cat(roots)
    # Preserve source floor height and centre X/Z at the beginning of the course.
    origin = roots[0].clone(); origin[1] = 0
    p = (p-origin) @ owner.course_axes
    roots = (roots-origin) @ owner.course_axes
    r = r @ owner.course_axes
    if not all(torch.isfinite(x).all() for x in (p, r, roots)):
        raise RuntimeError('Directional NN became non-finite')
    return dict(names=list(full.body_names), fps=30, duration=duration, phase=phase,
        gait=gait, direction=direction, periodSeconds=stride/30, poses=[dict(points=a, axes=b) for a,b in zip(p.tolist(),r.tolist())],
        roots=roots.tolist(), source='matching omni seed + autoregressive lower/upper NN',
        lowerInferences=start+count-1, upperInferences=start+count-warm-1,
        sourceSeedFrame=0, lowerSettleFrames=60, sourceStartFrame=start,
        command=owner.direction_info, directionMeta=owner.direction_info, referenceError=max_reference_error if reference_count else None,
        referenceSamples=reference_count, seconds=time.perf_counter()-started,
        provenance=owner.provenance)


@torch.inference_mode()
def resume_in_course(owner, request, max_frames=152):
    """Continue corrected course-space poses with the matching directional NN.

    All rotations remain row matrices. Transform both history poses AND the full
    commanded root window; otherwise backward motion would be fed as forward.
    The caller owns one serialized ResumeLocomotion worker and its lifetime.
    """
    if request.get('direction', 'forward') != owner.direction or request.get('policy', request['gait']) != owner.policy_gait:
        raise ValueError('Directional continuation context differs from the request')
    rotation = owner.course_axes
    inverse = rotation.T
    native = dict(request)
    native['roots'] = (torch.tensor(request['roots'], dtype=torch.float32) @ inverse).tolist()
    native['seeds'] = [dict(points=(torch.tensor(p['points'], dtype=torch.float32) @ inverse).tolist(),
                           axes=(torch.tensor(p['axes'], dtype=torch.float32) @ inverse).tolist())
                       for p in request['seeds']]
    result = owner.resume(native, max_frames=max_frames)
    result['roots'] = request['roots'][1:len(result['poses'])+1]
    for pose in result['poses']:
        pose['points'] = (torch.tensor(pose['points'], dtype=torch.float32) @ rotation).tolist()
        pose['axes'] = (torch.tensor(pose['axes'], dtype=torch.float32) @ rotation).tolist()
    # Preserve the exact user-authored seed across the floating-point basis trip.
    result['poses'][0] = dict(points=request['seeds'][1]['points'][1:], axes=request['seeds'][1]['axes'][1:])
    result.update(direction=owner.direction, directionMeta=owner.direction_info, command=owner.direction_info,
                  source='terrain-seeded directional lower + upper NN')
    return result


def command_seed(owner, drawn=False):
    """The same two settled initialization poses serve every new phase/turn.

    These are model initialization data, never a cached commanded rollout.
    Rebuild if source geometry, weights, native codecs or seed generation change.
    """
    mode = 1 if drawn else -1
    if not hasattr(owner, 'command_seeds'):
        owner.command_seeds = {}
    if mode in owner.command_seeds:
        return owner.command_seeds[mode]
    digest = hashlib.sha256(b'footik-command-seed-v1')
    for fn in (generate, decode_policy_rows, configure_direction):
        digest.update(inspect.getsource(fn).encode())
    digest.update(json.dumps(STRIDE_TICKS, sort_keys=True).encode())
    digest.update(json.dumps(owner.direction_sources, sort_keys=True).encode())
    digest.update(torch.__version__.encode())
    for path in [MODEL_ROOT/'locomotion.py', MODEL_ROOT/'models/provenance.json',
                 *[Path(m.__file__) for m in (runtime_data, runtime_data.lower_ctl,
                     upper_ctl, upper_data, cached_data, tl)]]:
        digest.update(path.read_bytes())
    fingerprint = digest.hexdigest()
    folder = ROOT/'.nn-cache';folder.mkdir(exist_ok=True)
    path = folder/f'seed-{owner.gait}-{mode}.json'
    seed = None
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            if saved['fingerprint'] == fingerprint:
                seed = saved['seed']
        except (OSError, ValueError, KeyError):
            pass  # A disposable interrupted cache must not break preparation.
    if seed is None:
        seed = generate(owner, dict(gait='run', direction=owner.direction,
                                    duration=.1, phase=0, drawn=drawn))
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(fingerprint=fingerprint, seed=seed),
                             separators=(',', ':'), allow_nan=False), encoding='utf-8')
        temporary.replace(path)
    owner.command_seeds[mode] = seed
    return seed


@torch.inference_mode()
def generate_command(owner, request):
    """Run policy at the requested speed, with actual turning root windows.

    Settle the recurrent history at command speed, then expose a phase-selected
    five-second segment. Yaw starts at visible time zero, so the final settling
    windows already contain the upcoming turn. Travel remains along course +Z.
    """
    gait, direction, duration, phase = validate(request)
    omega = float(request.get('rootYawSpeed', 0))
    yaw_start, yaw_stop = yaw_distance_options(request)
    if not math.isfinite(omega) or abs(omega) > 360 or owner.policy_gait != 'run':
        raise ValueError('Run policy and bounded root yaw required')
    started = time.perf_counter()
    seed = command_seed(owner, request.get('drawn', False))
    # Walk is a speed command, never the old Walk checkpoint. Native directional
    # walking commands match the recorded gallery: F200/B150/sides180 cm/s.
    speed = ({'forward': 2., 'backward': 1.5, 'left': 1.8, 'right': 1.8}[direction]
             if gait == 'walk' else owner.direction_info['commandSpeed'])
    stride = STRIDE_TICKS[gait][direction]/2
    start = 60 + round((phase % 1)*stride)
    count = math.ceil(duration*30)+2
    total = start+count
    current = torch.tensor(seed['roots'][1])
    roots = [seed['roots'][0]] + [(current+torch.tensor([0., 0., speed*k/30])).tolist()
                                 for k in range(total+8)]
    yaws = [yaw_command((k-1-start)/30, speed, omega, yaw_start, yaw_stop) for k in range(len(roots))]
    seeds = [dict(points=[seed['roots'][i], *seed['poses'][i]['points']],
                  axes=[torch.eye(3).tolist(), *seed['poses'][i]['axes']]) for i in (0, 1)]
    result = resume_in_course(owner, dict(gait=gait, policy='run', direction=direction,
        drawn=request.get('drawn', False), names=['root', *seed['names']], seeds=seeds,
        roots=roots, rootYawDegrees=yaws, frames=total,
        verifyReference=request.get('verifyReference', False)), max_frames=300)
    # Surface playback needs initial policy history, not a second five-second
    # rollout. Freeze capsule height from already-generated settled history so
    # extending the visible horizon cannot change the initial root trajectory.
    reference_height = None
    if request.get('seedOnly'):
        pelvis = result['names'].index('pelvis')
        history_start = max(0, start-math.ceil(stride))
        reference_height = sum(result['poses'][i]['points'][pelvis][1]-result['roots'][i][1]
                               for i in range(history_start, start))/(start-history_start)
    origin = torch.tensor(result['roots'][start]); origin[1] = 0
    result['poses'] = result['poses'][start:]
    result['pins'] = result['pins'][start:]
    for pose in result['poses']:
        pose['points'] = (torch.tensor(pose['points'])-origin).tolist()
    result['roots'] = (torch.tensor(result['roots'][start:])-origin).tolist()
    result['rootYawDegrees'] = result['rootYawDegrees'][start:]
    if result.get('rootFeatures') is not None:
        result['rootFeatures'] = result['rootFeatures'][start:]
    info = dict(owner.direction_info, commandSpeed=speed, policyGait='run', commandGait=gait)
    if reference_height is not None:
        info.update(referenceHeight=reference_height, totalDuration=float(request.get('totalDuration', 5)),
                    referenceHeightSource='mean pelvis-root height over final warmup gait period')
    result.update(gait=gait, duration=duration, phase=phase, directionMeta=info, command=info,
        periodSeconds=stride/30, rootYawSpeed=omega, nnRootWindow=True,
        rootYawStart=yaw_start, rootYawStop=yaw_stop,
        source='Run 181751 + Upper 82500 · root-window NN', provenance=owner.provenance,
        lowerSettleFrames=start, seconds=time.perf_counter()-started)
    return result


class DirectionalLocomotion(Locomotion):
    def __init__(self, gait, direction):
        super().__init__(gait)
        configure_direction(self, gait, direction)

    def generate(self, **request):
        return generate(self, dict(gait=self.policy_gait, direction=self.direction, **request))


if __name__ == '__main__':
    owner, key = None, None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            gait, direction, _, _ = validate(request)
            if key != (gait, direction):
                owner, key = DirectionalLocomotion(gait, direction), (gait, direction)
            result = generate(owner, request)
            print(json.dumps(result, separators=(',', ':'), allow_nan=False), flush=True)
        except Exception as error:
            print(json.dumps({'error': str(error)}), flush=True)
