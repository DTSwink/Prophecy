"""Replace the lab's Pike with pike_final, retaining its sword contact and timing."""
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
SOURCE = STEPPER / 'ue5/slashes/pike_final.fbx'


def export():
    manifest = json.loads((ROOT / 'data/manifest.json').read_bytes())
    vanilla = json.loads((ROOT / 'data/vanilla.json').read_bytes())
    old = next(c for c in vanilla['clips'] if c['name'] == 'pike')
    names, parents = manifest['names'], manifest['parents']
    hand, count = names.index('hand_r'), len(names)
    phases = old['phases'].copy()
    assert phases == {'armed': 9, 'hit': 16} and old['fps'] == 30
    # Preserve the established contact along the blade, not the obsolete world
    # target or a different point such as the rendered sword tip.
    contact = old.get('hitTargetSource')
    if contact and contact.get('kind') == 'retained-sword-contact':
        offset = np.array(contact['local'])
    else:
        raw = np.frombuffer((ROOT / old['file']).read_bytes(), dtype='<f4')
        points = raw[:old['frames'] * count * 3].reshape(old['frames'], count, 3)
        matrices = raw[old['frames'] * count * 3:].reshape(old['frames'], count, 3, 3).swapaxes(-1, -2)
        hit = int(phases['hit'])
        # Decode the float32 basis as a proper rotation, like the lab decoder.
        rotation = Rotation.from_matrix(matrices[hit, hand]).as_matrix()
        offset = rotation.T @ (np.array(old['hitTarget']) - points[hit, hand])
        contact = dict(kind='retained-sword-contact', bone='hand_r', local=offset.tolist(),
                       referenceClipSHA256=old['sha256'], referenceTarget=old['hitTarget'])
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    manager, scene = load_scene(SOURCE)
    try:
        original_axis, _, _ = normalize_scene_axis_system(scene)
        nodes = {n.GetName(): n for n in collect_skeleton_nodes(scene)}
        actual_parents = []
        for name in names:
            parent = nodes[name].GetParent()
            while parent and parent.GetName() not in names:
                parent = parent.GetParent()
            actual_parents.append(names.index(parent.GetName()) if parent else -1)
        assert actual_parents == parents, 'Pike rig hierarchy differs'
        times, fps, first, last = make_sample_times(scene)
        assert (fps, first, last, len(times)) == (30, 0, 17, 18), 'Pike timing changed'
        scale = scene.GetGlobalSettings().GetSystemUnit().GetScaleFactor() * .01
        points, quaternions = [], []
        for when in times:
            transforms = [nodes[name].EvaluateGlobalTransform(when) for name in names]
            points.append([[float(x) * scale for x in list(t.GetT())[:3]] for t in transforms])
            quaternions.append([list(t.GetQ()) for t in transforms])
        points = np.asarray(points)
        matrices = Rotation.from_quat(np.asarray(quaternions).reshape(-1, 4)).as_matrix().reshape(len(times), count, 3, 3)
        assert np.isfinite(points).all() and np.isfinite(matrices).all()
        np.testing.assert_allclose(np.linalg.det(matrices), 1, atol=1e-10)
        target = (points[int(phases['hit']), hand] + matrices[int(phases['hit']), hand] @ offset).tolist()
        raw = points.astype('<f4').tobytes() + matrices.swapaxes(-1, -2).astype('<f4').tobytes()
    finally:
        manager.Destroy()
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
    meta = dict(name='pike', file='data/vanilla/pike.bin', frames=len(times), fps=fps,
                phases=phases, hitTarget=target, hitTargetSource=contact, source=str(SOURCE),
                sourceSHA256=source_hash, sourceFrames=[first, last], sourceAxis=original_axis,
                sha256=hashlib.sha256(raw).hexdigest(), sourceOverride=True)
    vanilla['clips'] = [meta if c['name'] == 'pike' else c for c in vanilla['clips']]
    family = next(c for c in manifest['clips'] if c['name'] == 'pike')
    family.update(fps=fps, phases=phases, variants=[dict(meta, id=1, kind='authored', target=target, joints=count)])
    family['attackFrame0'] = dict(points=points[0].tolist(), axes=matrices[0].swapaxes(-1, -2).tolist(),
                                 source=str(SOURCE), sha256=source_hash, frame=0)
    (ROOT / meta['file']).write_bytes(raw)
    (ROOT / 'data/vanilla.json').write_text(json.dumps(vanilla, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'data/manifest.json').write_text(json.dumps(manifest, separators=(',', ':')), encoding='utf-8')
    print(json.dumps(meta, indent=2))


if __name__ == '__main__':
    export()
