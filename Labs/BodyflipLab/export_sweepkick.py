"""Append the authored recovery-folder sweep; never rewrite the original clips."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

STEPPER = Path('C:/Users/singerie/Documents/Cursor/stepper')
sys.path.insert(0, str(STEPPER / 'fbx_npz_pipeline'))
from fbx_to_npz import load_scene, collect_skeleton_nodes, make_sample_times, normalize_scene_axis_system

ROOT = Path(__file__).resolve().parent
SOURCE = STEPPER / 'ue5/slashes/recoveries/sweepKick.fbx'
NAME = 'sweepKick'
PHASES = dict(armed=8, hit=17)


def export():
    manifest = json.loads((ROOT / 'data/manifest.json').read_bytes())
    vanilla = json.loads((ROOT / 'data/vanilla.json').read_bytes())
    names, parents = manifest['names'], manifest['parents']
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    manager, scene = load_scene(SOURCE)
    try:
        original_axis, _, _ = normalize_scene_axis_system(scene)
        nodes = {n.GetName(): n for n in collect_skeleton_nodes(scene)}
        actual_parents = []
        for name in names:
            node = nodes[name].GetParent()
            while node and node.GetName() not in names:
                node = node.GetParent()
            actual_parents.append(names.index(node.GetName()) if node else -1)
        assert actual_parents == parents, 'Rig hierarchy differs'
        times, fps, first, last = make_sample_times(scene)
        assert first == 0 and len(times) > PHASES['hit']
        scale = scene.GetGlobalSettings().GetSystemUnit().GetScaleFactor() * .01
        points, quaternions = [], []
        for when in times:
            transforms = [nodes[name].EvaluateGlobalTransform(when) for name in names]
            points.append([[float(x) * scale for x in list(t.GetT())[:3]] for t in transforms])
            quaternions.append([list(t.GetQ()) for t in transforms])
        points = np.asarray(points)
        matrices = Rotation.from_quat(np.asarray(quaternions).reshape(-1, 4)).as_matrix().reshape(len(times), len(names), 3, 3)
        assert np.isfinite(points).all() and np.isfinite(matrices).all()
        np.testing.assert_allclose(np.linalg.det(matrices), 1, atol=1e-10)
        # Lab basis vectors are stored consecutively, i.e. matrix columns.
        raw = points.astype('<f4').tobytes() + matrices.swapaxes(-1, -2).astype('<f4').tobytes()
        # No authored target exists in this FBX. Use the established kick contact
        # point on the striking right foot at the user-specified Hit frame.
        foot, offset = names.index('foot_r'), np.array([.07, -.06, 0.])
        target = (points[17, foot] + matrices[17, foot] @ offset).tolist()
    finally:
        manager.Destroy()
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
    file = 'data/vanilla/sweepKick.bin'
    (ROOT / file).write_bytes(raw)
    meta = dict(name=NAME, file=file, frames=len(times), fps=fps, phases=PHASES,
                hitTarget=target, source=str(SOURCE), sourceSHA256=source_hash,
                sha256=hashlib.sha256(raw).hexdigest(), sourceFrames=[first, last],
                sourceAxis=original_axis, effector='foot_r', circular=True,
                hitTargetSource=dict(kind='derived-contact', bone='foot_r', local=offset.tolist(), frame=17))
    vanilla['clips'] = [c for c in vanilla['clips'] if c['name'] != NAME] + [meta]
    variant = dict(meta, id=1, kind='authored', target=target, joints=len(names))
    group = dict(name=NAME, fps=fps, variants=[variant], phases=PHASES)
    manifest['clips'] = [c for c in manifest['clips'] if c['name'] != NAME] + [group]
    (ROOT / 'data/vanilla.json').write_text(json.dumps(vanilla, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'data/manifest.json').write_text(json.dumps(manifest, separators=(',', ':')), encoding='utf-8')
    print(json.dumps(meta, indent=2))


if __name__ == '__main__':
    export()
