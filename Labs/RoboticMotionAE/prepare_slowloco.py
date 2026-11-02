"""Prepare the user's slowloco collection without changing existing cuts/models."""
import argparse
import json
import pickle
import shutil
from pathlib import Path

import numpy as np
import torch
import prepare as base
from features import encode, SCHEMA
from motion import load_dataset, read_motion, clip_record, save_dataset, atomic_json

ROOT = base.ROOT
OUT = ROOT / 'Saved/RoboticMotionAE/20261031_slowloco'
DATASET = Path.home() / 'Documents/Lafan Cutter/datasets/slowloco/dataset.json'
NATIVE = Path.home() / 'Documents/Cursor/stepper/ue5/slashes/recoveries'
ADDITIONS = ('agonising', 'agonising_idle', 'limpL', 'limpR', 'lying', 'sitting')


def append():
    from import_fbx import convert
    OUT.mkdir(parents=True, exist_ok=True)
    original = DATASET.read_bytes()
    before = OUT / 'dataset-before.json'
    if before.exists():
        raise RuntimeError('Import already attempted; inspect receipts instead of duplicating clips')
    before.write_bytes(original)
    _, cuts = load_dataset(DATASET)
    assert len(cuts) == 4
    reports = []
    for name in ADDITIONS:
        source = NATIVE / (name + '.fbx')
        digest = base.sha(source)
        folder = DATASET.parent / 'imports' / (name + '_' + digest[:12])
        folder.mkdir(parents=True, exist_ok=True)
        archived = folder / source.name
        shutil.copy2(source, archived)
        exported = folder / (name + '.bvh')
        receipt = convert(archived, exported)
        assert base.sha(source) == base.sha(archived) == digest
        receipt['original_source_fbx'] = str(source)
        atomic_json(folder / 'conversion.json', receipt)
        motion = read_motion(exported)
        cuts.append({**clip_record(motion, 0, motion.count - 1),
                     'label': name + ' · full clip', 'source_fbx': str(source),
                     'source_fbx_sha256': digest, 'archived_fbx': str(archived),
                     'conversion_report': str(folder / 'conversion.json')})
        reports.append(receipt)
        print(json.dumps({'converted': name, 'frames': motion.count, 'fps': motion.fps}), flush=True)
    assert DATASET.read_bytes() == original, 'User edited dataset during import'
    result = save_dataset(DATASET.parent.parent, 'slowloco', cuts)
    doc = json.loads(result.read_text(encoding='utf-8'))
    old = json.loads(original)
    assert [c['sha256'] for c in doc['clips'][:4]] == [c['sha256'] for c in old['clips']]
    assert len(doc['clips']) == 10
    atomic_json(OUT / 'import-receipt.json', dict(dataset=str(result), dataset_sha256=base.sha(result),
        existing_cut_hashes_unchanged=True, total_clips=10, added=list(ADDITIONS), conversions=reports))


def prepare():
    torch.set_num_threads(2)
    receipt = json.loads((OUT / 'import-receipt.json').read_text())
    assert base.sha(DATASET) == receipt['dataset_sha256']
    _, cuts = load_dataset(DATASET)
    data = OUT / 'data'
    data.mkdir(exist_ok=False)
    motions = OUT / 'motions'
    motions.mkdir(exist_ok=True)
    rt = base.rt
    model = rt.MJCFCharModel('cpu')
    model.load(str(rt.MODEL / 'humanoid_uefn.xml'))
    meta = json.loads((rt.MODEL / 'limits.json').read_text())
    rig = json.loads((ROOT / meta['source_rig']).read_text())
    old = json.loads((ROOT / 'Saved/LafanCrawlRetarget/manifest.json').read_text())
    # Reuse the exact accepted LAFAN robot exports only with identical model geometry.
    for path, digest in old['dependencies'].items():
        if base.sha(path) == digest:
            continue
        backup = ROOT / 'Saved/MimicKitCrawl/upperbody-limits-20261017/before'
        name = Path(path).name
        assert name in ('limits.json', 'source-rig.json') and base.sha(backup / name) == digest
        oldmeta = json.loads((backup / 'limits.json').read_text())
        for key in ('geometry', 'groups', 'body_frames', 'source_body_frames', 'parents', 'source_parents'):
            assert oldmeta[key] == meta[key], key
        assert json.loads((backup / 'source-rig.json').read_text())['bodies'] == rig['bodies']
    arrays, info, checks = {}, [], []
    for i, cut in enumerate(cuts):
        if not cut.get('source_fbx'):
            match = [m for m in old['motions'] if m['original_source_sha256'] == cut['source_sha256']]
            assert len(match) == 1
            source = Path(match[0]['robot_motion'])
            # The retained NPZ is an independent copy of the accepted coordinates.
            saved = pickle.loads(source.read_bytes())
            with np.load(source.with_suffix('.npz')) as audit:
                np.testing.assert_array_equal(saved['frames'], audit['frames'])
            path = motions / (str(i) + '_lafan.pkl')
            shutil.copy2(source, path)
            frames, fps = saved['frames'], saved['fps']
            assert len(frames) == cut['frames'] and abs(fps - cut['fps']) < 1e-8
            method = 'Reused accepted robotic LAFAN export; source cut hash exact'
        else:
            stem = f'{i:02d}_{Path(cut["source_fbx"]).stem}'
            frames, fps = base.shared.reduce_uefn(cut, model, meta, rig, motions, stem)
            path = motions / (stem + '_robotic.pkl')
            method = 'Existing native FBX body projection and foot correction'
        robot, p, r, times = base.shared.resample(model, frames, fps)
        assert np.isfinite(robot).all() and np.isfinite(p).all() and np.isfinite(r).all()
        checks.append(base.shared.preflight(p, r))
        np.savez_compressed(data / f'clip_{i}_30hz.npz', frames=robot, position=p, rotation=r)
        idx = np.arange(len(p)-2)[:, None] + np.arange(3)[None, :]
        features = encode(torch.from_numpy(p[idx]), torch.from_numpy(r[idx])).numpy()
        n = len(p)
        hold = max(3, int(n * .2))
        a = n - 2*hold - 4
        b = a + 2 + hold
        assert a >= 3, (i, n)
        splits, used = {}, []
        for name, (lo, hi) in dict(train=(0, a), validation=(a+2, b), test=(b+2, n)).items():
            starts = np.arange(lo, hi-2, dtype=np.int64)
            assert len(starts) > 0
            ids = set((starts[:, None] + np.arange(3)[None, :]).ravel())
            assert not any(ids & s for s in used)
            used.append(ids)
            arrays[f'{name}_{i}'] = features[starts]
            arrays[f'{name}_starts_{i}'] = starts
            splits[name] = dict(frame_interval=[lo, hi], windows=len(starts))
        info.append(dict(id=i, label=cut['label'], robot_motion=str(path), robot_sha256=base.sha(path),
                         source_sha256=cut['source_sha256'], frames_30hz=n, splits=splits, conversion=method))
        print(json.dumps(dict(prepared=cut['label'], frames=n, splits=splits)), flush=True)
    weights = np.full(len(cuts), 1/len(cuts), dtype=np.float64)
    mean = sum(weights[i]*arrays[f'train_{i}'].mean(0, dtype=np.float64) for i in range(len(cuts)))
    variance = sum(weights[i]*((arrays[f'train_{i}']-mean)**2).mean(0) for i in range(len(cuts)))
    floors = np.tile(np.r_[np.full(3, .02), np.full(6, .05)], 45)
    arrays.update(mean=mean.astype(np.float32), std=np.maximum(np.sqrt(variance), floors).astype(np.float32),
                  clip_weights=weights.astype(np.float32))
    np.savez_compressed(data / 'features.npz', **arrays)
    atomic_json(data / 'dataset.json', dict(schema=SCHEMA, input_dim=405, body_names=model.get_body_names(),
        hz=30, window_poses=3, clips=info, sampling='Uniform clips then windows; each of the 10 clips has 10% weight',
        split='Chronological roughly60/20/20 with two-frame gaps; no shared pose frames',
        normalization='Equal-clip training-only mean/std; floors .02m/.05 rotation',
        validation_limit='Within-motion holdouts, not independent-motion generalization',
        dataset_sha256=base.sha(DATASET), features_sha256=base.sha(data / 'features.npz'),
        model_sha256=base.sha(rt.MODEL / 'humanoid_uefn.xml')))
    atomic_json(data / 'preflight.json', dict(passed=True, clips=checks, disjoint_pose_frames=True,
        original_cuts_preserved=True, policy_training_unchanged=True))


def export():
    run = OUT / 'run_2x512'
    completed = json.loads((run / 'completed.json').read_text())
    config = json.loads((run / 'config.json').read_text())
    manifest = json.loads((OUT / 'data/dataset.json').read_text())
    assert completed['state'] == 'complete' and completed['clip_count'] == 10
    previous = ROOT / 'Saved/MotionRegularizer-2x512'
    contract = json.loads((previous / 'body_contract.json').read_text())
    assert base.sha(previous / 'robot.xml') == manifest['model_sha256']
    assert contract['body_names'] == manifest['body_names']
    assert (previous / 'motion_features.py').read_bytes() == Path(__file__).with_name('features.py').read_bytes()
    dest = OUT / 'bundle'
    dest.mkdir(exist_ok=False)
    for name in ('motion_scorer.pt', 'autoencoder.pt', 'validation.json'):
        shutil.copy2(run / name, dest / name)
    for name in ('robot.xml', 'body_contract.json', 'motion_features.py', 'smoke_test.py'):
        shutil.copy2(previous / name, dest / name)
    state = torch.load(run / 'best.pt', map_location='cpu', weights_only=False)
    np.savez(dest / 'normalization.npz', mean=state['mean'].numpy(), std=state['std'].numpy())
    positions, rotations = [], []
    for i in (0, 4, 7, 9):
        clip = np.load(OUT / 'data' / f'clip_{i}_30hz.npz')
        start = manifest['clips'][i]['splits']['test']['frame_interval'][0]
        positions.append(clip['position'][start:start+3])
        rotations.append(clip['rotation'][start:start+3])
    np.savez(dest / 'example_windows.npz', positions=np.stack(positions), rotations=np.stack(rotations))
    atomic_json(dest / 'model_info.json', dict(name='Slow loco motion AE',
        architecture='405 -> 512 -> 512 -> 128 -> 512 -> 512 -> 405', schema=SCHEMA,
        training=config, results=completed, dataset_sha256=manifest['dataset_sha256'],
        clips=[c['label'] for c in manifest['clips']], policy_integration=False))
    (dest / 'README.md').write_text('''# Slow loco motion AE

Separate frozen AE trained on all ten clips in the user's slowloco dataset.
Two LAFAN selections, crawl, crawl_idle, agonising, agonising_idle, limpL,
limpR, lying and sitting. Each clip has equal sampling weight. Existing
source cuts are preserved; native FBXs use the established physical-body
projection/foot correction. This model has not been installed into a policy.

Use motion_features.encode with three consecutive 30 Hz physical poses,
15 body origins in world metres/Z-up and proper rotation matrices, in the
body_contract.json order. The fixed oldest-pelvis heading/XY frame retains
height, tilt and movement. No history across resets or clip boundaries.
motion_scorer.pt includes normalization and returns reconstruction MSE;
autoencoder.pt accepts normalized features. Freeze weights, retain input
gradients if needed. Run smoke_test.py to check portable CPU loading.

Selected by lowest validation loss within 12,000 updates. Chronological
within-clip holdouts have disjoint frames but are not independent motions;
short periodic clips have few test windows. Synthetic corruption diagnostics
do not establish controller quality. See model_info.json and validation.json.
''', encoding='utf-8')
    atomic_json(dest / 'checksums.json', {p.name: base.sha(p) for p in dest.iterdir() if p.is_file()})
    print(str(dest), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['append', 'prepare', 'export'])
    args = parser.parse_args()
    globals()[args.stage]()
