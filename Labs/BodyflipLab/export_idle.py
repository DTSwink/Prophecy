"""Copy the already-frozen neutral idle into Bodyflip's local animation format."""
import hashlib
import json
from pathlib import Path
import numpy as np

root = Path(__file__).resolve().parent
source = root.parent / 'AttackRecoveryLab/frozen/neutral_idle.npz'
manifest = json.loads((root / 'data/manifest.json').read_text())
with np.load(source, allow_pickle=False) as data:
    assert list(data['bone_names']) == manifest['names']
    assert data['parents'].tolist() == manifest['parents']
    points = data['global_joint_pos'].astype('<f4') * .01
    axes = data['global_matrix'][:, :, :3, :3].astype('<f4')
    assert np.allclose(points[0], manifest['sharedIdle']['points'], atol=1e-6)
    assert np.allclose(axes[0], manifest['sharedIdle']['axes'], atol=1e-6)
    (root / 'data/idle.bin').write_bytes(points.tobytes() + axes.tobytes())
    meta = dict(frames=len(points), fps=float(data['fps']), file='data/idle.bin',
                asset=manifest['sharedIdle']['unrealAsset'],
                sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    (root / 'data/idle.json').write_text(json.dumps(meta, indent=2) + '\n')
print(json.dumps(meta))
