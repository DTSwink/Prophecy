"""Read-only extraction of the four authored three-frame recovery poses."""
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


def main():
    manifest = json.loads((ROOT / 'data/manifest.json').read_bytes())
    names, parents = manifest['names'], manifest['parents']
    clips = []
    for slot, name in enumerate(['lara', 'snatch', 'ball', 'ninja'], 1):
        source = STEPPER / f'ue5/slashes/recoveries/pose_{name}.fbx'
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        manager, scene = load_scene(source)
        try:
            axis, _, _ = normalize_scene_axis_system(scene)
            nodes = {n.GetName(): n for n in collect_skeleton_nodes(scene)}
            actual_parents = []
            for name_in_rig in names:
                parent = nodes[name_in_rig].GetParent()
                while parent and parent.GetName() not in names:
                    parent = parent.GetParent()
                actual_parents.append(names.index(parent.GetName()) if parent else -1)
            assert actual_parents == parents, 'Rig hierarchy differs'
            times, fps, first, last = make_sample_times(scene)
            assert first == 0 and last == 2 and len(times) == 3
            scale = scene.GetGlobalSettings().GetSystemUnit().GetScaleFactor() * .01
            frames = []
            for when in times:
                transforms = [nodes[n].EvaluateGlobalTransform(when) for n in names]
                points = [[float(x) * scale for x in list(t.GetT())[:3]] for t in transforms]
                q = [[float(x) for x in t.GetQ()] for t in transforms]
                matrices = Rotation.from_quat(q).as_matrix()
                assert np.isfinite(points).all() and np.isfinite(matrices).all()
                np.testing.assert_allclose(np.linalg.det(matrices), 1, atol=1e-10)
                frames.append(dict(points=points, q=q))
        finally:
            manager.Destroy()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        clips.append(dict(id=f'pose{slot}', name=name.title(), source=str(source),
                          sourceSHA256=digest, sourceAxis=axis, fps=fps,
                          sourceFrames=[first, last], neutralFrame=0, positiveFrame=1 if name == 'lara' else 2, negativeFrame=2 if name == 'lara' else 1, frames=frames))
    output = dict(schema='bodyflip-authored-poses-v1', names=names, parents=parents, clips=clips)
    (ROOT / 'data/poses.json').write_text(json.dumps(output, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps([dict(id=c['id'], name=c['name'], frames=len(c['frames']), sha256=c['sourceSHA256']) for c in clips]))


if __name__ == '__main__':
    main()
