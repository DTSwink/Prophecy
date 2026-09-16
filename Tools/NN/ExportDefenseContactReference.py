"""Export immutable parry collider geometry and its saved contact witness."""
from pathlib import Path
import json
import sys
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/parry_unreal_reference_770015')
STAGED = ROOT/'Saved/DefenseIntegration/ReferenceSources/parry/training/slashes2/ParryAndDodge'
DEST = ROOT/'Saved/DefenseIntegration/Models'
sys.path.insert(0, str(STAGED))
from transition_geometry import load_geometry
from frozen_parry_forearm_geometry import thin_forearms


def main():
    torch.set_num_threads(1)
    skeleton = json.loads((SOURCE/'skeleton.json').read_text())
    names = skeleton['joint_names']
    geometry = thin_forearms(load_geometry(names, parry=True, path=SOURCE/'collider_catalog.json'))
    base = geometry.base
    records = []
    for i, name in enumerate(geometry.names):
        record = dict(name=name, half=geometry.half_sizes_m[i].tolist(), center_offset=geometry.center_offsets_local[i].tolist())
        if i < base.count:
            record.update(bone=int(base.bone_indices[i]), offset=base.offsets_m[i].tolist(), axes=base.local_axes[i].flatten().tolist())
        records.append(record)
    (DEST/'parry_colliders.json').write_text(json.dumps(dict(version=1, base_count=base.count, colliders=records), indent=2)+'\n')
    expected = json.loads((SOURCE/'parity_expected.json').read_text())
    inputs = json.loads((SOURCE/'inputs.json').read_text())
    e = inputs['episode']
    count = len(expected['trajectory/positions'])
    def flat(v): return np.asarray(v, dtype=np.float32).reshape(-1).tolist()
    frames = [dict(positions=flat(expected['trajectory/positions'][i]), rotations=flat(expected['trajectory/basis'][i]),
                   centers=flat(expected['colliders/centers'][i]), axes=flat(expected['colliders/axes'][i]),
                   attacker_center=flat(e['collider'][0][i][:3]), attacker_axes=flat(e['collider_axes'][0][i]),
                   time=float(e['times'][0][i])) for i in range(count)]
    document = dict(frames=frames, attacker_half=flat(e['attack_half']), blocking=['blade'],
                    expected_protected=expected['contact/protected'], expected_time=expected['contact/first_block_time'])
    (DEST/'parry_contact_reference.json').write_text(json.dumps(document)+'\n')
    print(f'Exported {len(records)} colliders and {count} completed frames; expected block {document["expected_time"]}.')


if __name__ == '__main__': main()
