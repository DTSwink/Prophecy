"""Export the original Headbutt's pre-Armed arm targets; never change training data."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from ExportProphecySlashPolicy import PROJECT, prepare, slash, torch, sha, CHECKPOINT_SHA

torch.set_num_threads(2)
rt, _, _, _ = prepare(1)
source = next(p for p in Path(rt.recipe.gt_dir).glob('*.npz') if p.stem.lower() == 'headbutt')
original = source.parent.parent / 'final_gt_attack_dataset_npz' / source.name
gt = slash.load_controller_target_arrays(source)
with np.load(source, allow_pickle=False) as z:
    armed, fps = int(z['attack_armed_frame']), float(z['fps'])
with np.load(original, allow_pickle=False) as z:
    assert armed == float(z['attack_armed_frame']) and fps == float(z['fps'])
assert armed == 7 and fps == 30
pelvis = gt.names.index('pelvis')
rows = []
for frame in range(armed + 1):
    p = gt.visible_global_pos_m[frame, pelvis]
    inv = gt.controller_global_rot[frame, pelvis].T
    arms = []
    for side in ('l', 'r'):
        hand, upper = [gt.names.index(n + '_' + side) for n in ('hand', 'upperarm')]
        pos = (gt.visible_global_pos_m[frame, hand] - p) @ inv
        rotations = np.stack([gt.controller_global_rot[frame, i] @ inv for i in (hand, upper)])
        quat = Rotation.from_matrix(rotations.transpose(0, 2, 1)).as_quat()
        # Verify the serialized quaternion convention reconstructs source row bases.
        assert np.max(np.abs(Rotation.from_quat(quat).as_matrix().transpose(0, 2, 1) - rotations)) < 1e-5
        arms.append(np.concatenate((pos, quat.reshape(-1))).tolist())
    rows.append(arms)
dest = PROJECT / 'Content/locomotion/NN/prophecy_headbutt_preparation.json'
dest.write_text(json.dumps(dict(schema=1, checkpoint_sha256=CHECKPOINT_SHA, fps=fps,
    armed_frame=armed, source_sha256=sha(source), original_sha256=sha(original),
    frames=rows), separators=(',', ':')) + '\n', encoding='utf-8')
print(json.dumps(dict(path=str(dest), frames=len(rows), bytes=dest.stat().st_size)))
