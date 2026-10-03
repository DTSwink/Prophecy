"""Extract authored idle, phase labels and sword geometry without modifying sources."""
import json
import re
import hashlib
import shutil
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent

def main():
    text = (ROOT / 'frozen/source.html').read_text(encoding='utf-8')
    match = re.search(r'const basePayload\s*=\s*', text)
    payload, _ = json.JSONDecoder().raw_decode(text[match.end():])
    (ROOT / 'data/sword.json').write_text(json.dumps(payload.get('sword')), encoding='utf-8')
    manifest_path = ROOT / 'data/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    idle_source = ROOT.parent / 'walk_run_sword_prep/authored_pruned_npz/walk_omni/M_Neutral_Stand_Idle_Loop.npz'
    frozen_idle = ROOT / 'frozen/neutral_idle.npz'
    if not frozen_idle.exists():
        shutil.copy2(idle_source, frozen_idle)
    with np.load(frozen_idle, allow_pickle=True) as data:
        assert list(map(str, data['bone_names'])) == manifest['names']
        assert data['parents'].tolist() == manifest['parents']
        assert int(data['axis_up_axis']) == 2
        common_idle = {
            'points': (data['global_joint_pos'][0].astype(float) * .01).tolist(),
            'axes': data['global_matrix'][0, :, :3, :3].astype(float).tolist(),
            'source': str(idle_source), 'frozenSource': str(frozen_idle.relative_to(ROOT)),
            'sha256': hashlib.sha256(frozen_idle.read_bytes()).hexdigest(), 'frame': 0,
            'unrealAsset': '/Game/_mygame/M_Neutral_Stand_Idle_Loop',
        }
    manifest['sharedIdle'] = common_idle
    for clip in manifest['clips']:
        source = ROOT.parent / 'controller_dof_candidate_gt32_v1' / (clip['name'] + '.npz')
        frozen_source = ROOT / 'frozen/idle_source' / source.name
        frozen_source.parent.mkdir(exist_ok=True)
        if not frozen_source.exists():
            shutil.copy2(source, frozen_source)
        with np.load(frozen_source, allow_pickle=True) as data:
            clip['attackFrame0'] = {
                'points': data['model_global_joint_pos_m'][0].astype(float).tolist(),
                'axes': data['model_global_matrix'][0, :, :3, :3].astype(float).tolist(),
                'source': str(source), 'frozenSource': str(frozen_source.relative_to(ROOT)),
                'sha256': hashlib.sha256(frozen_source.read_bytes()).hexdigest(), 'frame': 0,
            }
            clip['idle'] = common_idle
            clip['phases'] = {'armed': int(data['attack_armed_frame']), 'hit': int(data['attack_hit_frame'])}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Prepared shared neutral idle, attack frame-0 references, phases and sword for', len(manifest['clips']), 'attacks')

if __name__ == '__main__':
    main()
