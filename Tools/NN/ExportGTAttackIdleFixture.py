"""Bake idle frame zero and original GT targets for the optional Blueprint loop.

Reads source NPZs only. Does not export weights or any future attack poses.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[2]
SOURCE = Path('C:/Users/singerie/Documents/Cursor/stepper/training/slashes2')
ATTACKS = ('jabL', 'jabR', 'hookL', 'hookR', 'overL', 'overR', 'headbutt',
           'kickL', 'kickR', 'slashL', 'slashR', 'slashLD', 'slashRD', 'slashLU', 'slashRU', 'pike')


def provenance(path):
    return dict(file=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    idle = SOURCE/'walk_run_sword_prep/authored_pruned_npz/walk_omni/M_Neutral_Stand_Idle_Loop.npz'
    names = json.loads((PROJECT/'Content/locomotion/NN/prophecy_slash_native.json').read_text())['bone_names']
    with np.load(idle, allow_pickle=False) as z:
        source_names = list(z['bone_names'])
        root = source_names.index('root')
        keep = [source_names.index(n) for n in names]
        matrix = z['global_matrix'][0].astype(np.float64)
        origin, basis = matrix[root, 3, :3], matrix[root, :3, :3]
        positions = ((matrix[keep, 3, :3]-origin) @ basis.T / 100).tolist()
        rotations = (matrix[keep, :3, :3] @ basis.T).tolist()
        assert float(z['system_unit_scale_factor_cm']) == 1 and int(z['frame_start']) == 0
    rows = {}
    files = {p.stem.lower(): p for p in (SOURCE/'final_gt_attack_dataset_npz').glob('*.npz')}
    for attack in ATTACKS:
        path = files[attack.lower()]
        with np.load(path, allow_pickle=False) as z:
            root = list(z['bone_names']).index('root')
            frame = z['global_matrix'][0, root].astype(np.float64)
            target = z['attack_target_world_m'].astype(np.float64)
            local = (target-frame[3, :3]/100) @ frame[:3, :3].T
            assert np.isfinite(local).all() and float(z['system_unit_scale_factor_cm']) == 1
            assert np.max(np.abs(local @ frame[:3, :3]+frame[3, :3]/100-target)) < 1e-6
            rows[attack.lower()] = dict(**provenance(path), target_local_cm=(local*[100, -100, 100]).tolist(),
                target_source_m=target.tolist(), armed_frame=float(z['attack_armed_frame']),
                hit_frame=float(z['attack_hit_frame']))
    result = dict(schema=1, idle=dict(**provenance(idle), frame=0), families=rows,
        rule='Idle frame 0 in both NN histories; each original target relative to its source frame-0 root, mapped onto the live agent carrier.',
        initial_history=dict(bone_names=names, positions=[positions, positions], rotations=[rotations, rotations]))
    dest = PROJECT/'Tools/NN/Fixtures/GTAttackIdle.json'
    dest.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(f'Wrote {dest}: {len(names)} bones, {len(rows)} original targets, idle frame 0 twice.')


if __name__ == '__main__':
    main()
