"""One-time native lower cache from the EXACT neural bank that authored a row.

This reads attested, already inferred walk/run poses, not defended dataset body
targets. No network (lower, upper or AE) is evaluated. The future upper baseline
is reconstructed only from lower FK; recorded neural upper motion is discarded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for _directory in (HERE, ROOT, ROOT / 'DefenseHarness'):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))
import train_imitation_smoke as native

SCHEMA = 'parry_accepted_walk_run_frozen_lower_cache_v1'
LOWER_NAMES = ('pelvis', 'thigh_l', 'calf_l', 'foot_l', 'ball_l',
               'thigh_r', 'calf_r', 'foot_r', 'ball_r')
ACCEPTED = {
    'walk': '860934962ad94894e5af1262dd403d85da46733e02a6be4afc09cf5e1197f64e',
    'run': 'ccc03fee15e825ebcbcd24f9e71934d515b5133e760114abe664445042d379c1',
}
POSITION_TOLERANCE_M = 2e-4
ROOT_TOLERANCE = 2e-5


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def checked_path(root, relative):
    root = Path(root).resolve()
    result = (root / relative).resolve()
    if not result.is_relative_to(root):
        raise ValueError('Frozen asset escaped its recorded bundle')
    return result


def integer_frames(times, frame_count):
    values = np.asarray(times, dtype=np.float64)
    rounded = np.rint(values)
    if (not np.isfinite(values).all() or
            not np.allclose(values, rounded, rtol=0, atol=1e-7)):
        raise ValueError('Frozen lower cache requires exact integer source frames; no approximate interpolation')
    result = rounded.astype(np.int64)
    if np.any(result < 0) or np.any(result >= frame_count):
        raise ValueError('Episode exceeds its attested frozen lower rollout')
    return result


class FrozenPreviewReader:
    """Read-only mmap plus exact source/hash validation, once per dataset bundle."""
    def __init__(self, dataset):
        self.dataset = Path(dataset)
        self.manifest_path = self.dataset / 'manifest.json'
        self.manifest = read(self.manifest_path)
        self.root = Path(self.manifest['frozen_inputs'])
        hashes = self.manifest['source_hashes']
        catalog_path = checked_path(self.root, 'packed_catalog.json')
        if digest(catalog_path) != hashes['packed_catalog.json']:
            raise ValueError('Recorded frozen catalog hash changed')
        self.catalog = read(catalog_path)
        identity = self.catalog['neural_bank']
        # The path may name a mutable manifest. Its recorded content hash, not
        # its name/default/current noise, is authoritative. Never fall back to
        # a different bank when this manifest has subsequently changed.
        candidates = [Path(identity['manifest'])]
        preview_root = ROOT / 'DefenseHarness' / 'neural_preview_npz'
        candidates.extend(preview_root.glob('bank_*/manifest*.json'))
        wanted = identity['manifest_sha256'].lower()
        selected = next((p for p in candidates if p.is_file() and digest(p) == wanted), None)
        if selected is None:
            raise ValueError(f'Original neural manifest {wanted} unavailable; no current-bank substitution')
        self.preview_manifest = read(selected)
        self.preview_manifest_path = selected
        self.provenance = dict(bundle=str(self.root), catalog_sha256=hashes['packed_catalog.json'],
            preview_manifest_sha256=wanted, neural_bank=identity['key'], assets={})
        source = self.preview_manifest['source_identity']
        for category, expected in ACCEPTED.items():
            if source[category + '_checkpoint']['sha256'].lower() != expected:
                raise ValueError(f'Unaccepted {category} checkpoint in original lower bank')
        self.provenance['checkpoints'] = {k: source[k + '_checkpoint'] for k in ACCEPTED}
        self.bone_names = tuple(self.catalog['bone_names'])
        self.positions = self._map('defense_file', (len(self.bone_names), 3), hashes)
        self.rotations = self._map('defense_basis_file', (len(self.bone_names), 3, 3), hashes)

    def _map(self, field, shape, hashes):
        relative = self.catalog[field]
        path = checked_path(self.root, relative)
        expected = hashes[relative]
        if digest(path) != expected:
            raise ValueError(f'Original inferred lower bank changed: {relative}')
        width = int(np.prod(shape)) * 4
        if path.stat().st_size % width:
            raise ValueError('Truncated frozen lower bank')
        self.provenance['assets'][relative] = expected
        return np.memmap(path, mode='r', dtype='<f4', shape=(path.stat().st_size // width, *shape))

    def sample(self, record, times, roots):
        scene = record['scene']
        if scene['locomotionBank'] != self.catalog['neural_bank']['key']:
            raise ValueError('Row names a different neural bank')
        index = int(scene['locomotionIndex'])
        row = self.catalog['defenses'][index]
        preview = self.preview_manifest['cases'][index]
        if row['file'] != record['source_defense'] or Path(preview['file']).name != row['file']:
            raise ValueError('Row preview filename/index mismatch')
        if scene.get('locomotionFile', row['file']) != row['file']:
            raise ValueError('Row scene preview filename mismatch')
        for key, value in row['preview'].items():
            if key not in preview or preview[key] != value:
                raise ValueError(f'Original preview metadata mismatch: {key}')
        category = preview['category']
        if preview['lower_checkpoint_sha256'].lower() != ACCEPTED[category]:
            raise ValueError('Row lower checkpoint identity mismatch')
        frames = integer_frames(times, int(row['frame_count'])) + int(row['frame_offset'])
        positions = np.array(self.positions[frames], dtype=np.float32, copy=True)
        rotations = np.array(self.rotations[frames], dtype=np.float32, copy=True)
        root_index = self.bone_names.index('root')
        actual_roots = np.concatenate((positions[:, root_index], rotations[:, root_index].reshape(-1, 9)), -1)
        if not np.allclose(actual_roots, np.asarray(roots), rtol=0, atol=ROOT_TOLERANCE):
            raise ValueError('Episode roots differ from original unperturbed locomotion')
        return positions, rotations, dict(file=row['file'], category=category,
            source_relative=preview['source_relative'], source_start_frame=preview['source_start_frame'],
            lower_checkpoint_sha256=ACCEPTED[category], bank=self.provenance['neural_bank'])


@torch.no_grad()
def encode_lower_baseline(positions, rotations, roots, names, skeleton, device='cpu'):
    """Encode lower context, retain exact recorded legs, build lower-only upper seed."""
    device = torch.device(device)
    roots = torch.as_tensor(roots, device=device, dtype=torch.float32)
    points = torch.as_tensor(positions, device=device, dtype=torch.float32)
    axes = torch.as_tensor(rotations, device=device, dtype=torch.float32)
    indices = [names.index(name) for name in skeleton.body_names]
    points, axes = points[:, indices], axes[:, indices]
    root_axes = roots[:, 3:].reshape(-1, 3, 3)
    inverse = torch.linalg.inv(root_axes)
    local_points = (points - roots[:, None, :3]) @ inverse
    local_axes = axes @ inverse[:, None]
    # This existing codec decodes upper as well, but the upper value is thrown
    # away immediately. ONLY the nine lower joints determine the 41-D state.
    body = torch.cat((local_points, local_axes[..., :2, :].flatten(-2)), -1)
    lower, _ = native.body_to_agent_states({'body': body.cpu().numpy()}, skeleton, device)
    ids = torch.zeros(len(lower), dtype=torch.long, device=device)
    base, decoded_pos, decoded_rot = native.slash2.base_upper_with_globals_from_lower(
        skeleton.runtime, ids, lower, roots[:, :3], root_axes)
    lower_indices = [skeleton.body_names.index(name) for name in LOWER_NAMES]
    error = (decoded_pos[:, lower_indices] - points[:, lower_indices]).abs().amax().item()
    rotation_error = (decoded_rot[:, lower_indices] - axes[:, lower_indices]).abs().amax().item()
    # A 41-D lower state has IK endpoints/start bases, not explicit knees. A
    # second solve with today's geometry can move the *intermediate* knee even
    # with identical endpoints (e.g. pack row294: 2.076mm). It is not the frozen
    # policy's output and must never replace the attested preview's legs.
    # Only pelvis drives the upper FK. Check its connection strictly; preserve
    # every lower world transform verbatim and record round-trip diagnostics.
    pelvis = skeleton.body_names.index('pelvis')
    pelvis_error = (decoded_pos[:, pelvis]-points[:, pelvis]).abs().amax().item()
    pelvis_rotation_error = (decoded_rot[:, pelvis]-axes[:, pelvis]).abs().amax().item()
    if (not np.isfinite(error+rotation_error) or pelvis_error > POSITION_TOLERANCE_M
            or pelvis_rotation_error > 2e-3):
        raise ValueError('Frozen lower codec changed the pelvis/upper-body attachment')
    decoded_pos[:, lower_indices] = points[:, lower_indices]
    decoded_rot[:, lower_indices] = axes[:, lower_indices]
    return dict(lower=lower.cpu(), roots=roots.cpu(), positions=decoded_pos.cpu(),
                rotations=decoded_rot.cpu(), baseline_upper=base.cpu()), dict(
                    max_position_error_m=0., max_rotation_element_error=0.,
                    codec_intermediate_position_error_m=error,
                    codec_intermediate_rotation_error=rotation_error)


def code_identity():
    paths = [Path(__file__), Path(native.__file__), Path(native.slash2.__file__),
             Path(native.tl.__file__), Path(native.ik_ctl.__file__)]
    # Content attestation must survive copying this release to RunPod. Absolute
    # Windows paths are not a code identity and differ on the Linux host.
    return {p.name: digest(p) for p in paths}


def load_cache(path, pack_path):
    cache = torch.load(path, map_location='cpu', weights_only=False)
    if cache['schema'] != SCHEMA or cache['source_pack_sha256'] != digest(pack_path):
        raise ValueError('Frozen lower cache belongs to another pack/schema')
    if cache['code_identity'] != code_identity():
        raise ValueError('Frozen lower codec changed; build a separately named cache')
    if cache['pin_metadata']['available']:
        raise ValueError('This preview cache must not invent unavailable pin commands')
    return cache


@torch.no_grad()
def build_cache(pack_path, output_path, *, indices=None, device='cpu'):
    """Build a separate lossless CPU tensor cache, retaining original row order.

    Existing files are reused only for identical source/code/row identities.
    They are never overwritten. ``indices`` exists for bounded parity audits.
    """
    pack_path, output_path = Path(pack_path), Path(output_path)
    pack = torch.load(pack_path, map_location='cpu', weights_only=False)
    if pack['kind'] != 'parry':
        raise ValueError('Frozen upper-only experiment is Parry only')
    selected = list(range(len(pack['rows']))) if indices is None else list(indices)
    if not selected or len(set(selected)) != len(selected) or any(i < 0 or i >= len(pack['rows']) for i in selected):
        raise ValueError('Select unique valid motion rows')
    if output_path.exists():
        existing = load_cache(output_path, pack_path)
        if existing['indices'] != selected:
            raise ValueError('Existing frozen cache selects different rows')
        return dict(path=str(output_path), cache_hit=True, rows=len(selected), audit=existing['audit'])
    started = time.monotonic()
    readers = {}
    for index in selected:
        dataset = pack['rows'][index]['row']['dataset']
        if dataset not in readers:
            readers[dataset] = FrozenPreviewReader(dataset)
    values, entries = {}, [None] * len(selected)
    errors = dict(max_position_error_m=0., max_rotation_element_error=0.,
                  codec_intermediate_position_error_m=0., codec_intermediate_rotation_error=0.)
    maximum = int(pack['maximum'])
    ordered = sorted(enumerate(selected), key=lambda item: pack['rows'][item[1]]['geometry'])
    skeleton = None
    previous_geometry = None
    for ordinal, (slot, index) in enumerate(ordered):
        row = pack['rows'][index]
        geometry = int(row['geometry'])
        if geometry != previous_geometry:
            source = pack['sources'][geometry]
            source_path = Path(source['path'])
            if digest(source_path) != source['sha256']:
                raise ValueError('Original source skeleton changed')
            prototype = pack['prototype']
            case = native.MotionCase(0, prototype['data'], row['record'], prototype['manifest'],
                                     source_path, prototype['data'], Path('.'))
            skeleton = native.build_skeleton(case, torch.device(device))
            previous_geometry = geometry
        count = int(row['length'])
        times = pack['episode']['times'][index, :count].numpy()
        roots = pack['episode']['authored_roots'][index, :count]
        reader = readers[row['row']['dataset']]
        points, axes, provenance = reader.sample(row['record'], times, roots.numpy())
        try:
            result, audit = encode_lower_baseline(points, axes, roots, reader.bone_names, skeleton, device)
        except ValueError as exc:
            raise ValueError(f'Pack row {index}, geometry {geometry}, source {row["row"]}: {exc}') from exc
        for name in errors:
            errors[name] = max(errors[name], audit[name])
        for name, tensor in result.items():
            if name not in values:
                values[name] = torch.empty((len(selected), maximum, *tensor.shape[1:]), dtype=tensor.dtype)
            values[name][slot, :count].copy_(tensor)
            values[name][slot, count:].copy_(tensor[-1:])
        entries[slot] = dict(pack_index=index, source_motion=row['row'], length=count, **provenance)
        if (ordinal + 1) % 250 == 0:
            print(json.dumps(dict(frozen_lower_cached=ordinal + 1, of=len(selected),
                                  seconds=round(time.monotonic() - started, 1))), flush=True)
    cache = dict(schema=SCHEMA, source_pack_sha256=digest(pack_path), code_identity=code_identity(),
        indices=selected, rows=entries, tensors=values, body_names=list(skeleton.body_names),
        lower_names=list(LOWER_NAMES), provenance={key: reader.provenance for key, reader in readers.items()},
        pin_metadata=dict(available=False, reason='Original inferred preview stores poses, not pin logits; foot-pin loss is disabled'),
        lower_source='attested_accepted_checkpoint_inference_not_defended_gt',
        baseline_source='native_lower_fk_upper_seed_exact_attested_legs_no_future_upper_motion', audit=errors)
    if any(not torch.isfinite(t).all() for t in values.values()):
        raise ValueError('Nonfinite frozen lower cache')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive publication protects existing immutable caches. Save directly
    # under a new name; on error this uncommitted partial cache is never reused.
    with output_path.open('xb') as stream:
        torch.save(cache, stream)
    return dict(path=str(output_path), cache_hit=False, rows=len(selected), audit=errors,
                seconds=round(time.monotonic() - started, 2), bytes=output_path.stat().st_size)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    chosen = list(range(args.limit)) if args.limit else None
    print(json.dumps(build_cache(args.pack, args.output, indices=chosen, device=args.device)), flush=True)
