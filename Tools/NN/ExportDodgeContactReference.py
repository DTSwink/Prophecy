"""Export the saved Dodge's 13 colliders, without Parry's extra/thinned boxes."""
from pathlib import Path
import json
import sys
import torch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/dodge_unreal_reference/reference')
DEST = ROOT/'Saved/DefenseIntegration/Models'
sys.path.insert(0, str(ROOT/'Saved/DefenseIntegration/ReferenceSources/dodge/training/slashes2/ParryAndDodge'))
from transition_geometry import load_geometry, defense_obbs


def main():
    torch.set_num_threads(1)
    skeleton = json.loads((SOURCE/'skeleton.json').read_text())
    catalog = DEST/'dodge_collider_catalog.json'
    catalog.write_text(json.dumps(skeleton['collider_catalog'])+'\n')
    geometry = load_geometry(skeleton['joint_names'], parry=False, path=catalog)
    base = geometry.base
    records = [dict(name=name, half=geometry.half_sizes_m[i].tolist(),
                    center_offset=geometry.center_offsets_local[i].tolist(),
                    bone=int(base.bone_indices[i]), offset=base.offsets_m[i].tolist(),
                    axes=base.local_axes[i].flatten().tolist()) for i, name in enumerate(geometry.names)]
    (DEST/'dodge_colliders.json').write_text(json.dumps(dict(version=1, base_count=base.count, colliders=records), indent=2)+'\n')
    motion = json.loads((SOURCE/'rollout.json').read_text())
    positions = torch.tensor(motion['positions'], dtype=torch.float32)
    rotations = torch.tensor(motion['basis'], dtype=torch.float32)
    centers, axes = defense_obbs(positions, rotations, geometry)
    frames = [dict(positions=positions[i].flatten().tolist(), rotations=rotations[i].flatten().tolist(),
                   centers=centers[i].flatten().tolist(), axes=axes[i].flatten().tolist())
              for i in range(motion['length'])]
    (DEST/'dodge_contact_reference.json').write_text(json.dumps(dict(frames=frames))+'\n')
    print(f'Exported {base.count} Dodge colliders and {len(frames)} saved pose samples.')


if __name__ == '__main__':
    main()
