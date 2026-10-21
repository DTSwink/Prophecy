"""Use the single current PHAT export; never restore historical joint profiles."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'Labs/MimicKitUEFN'
FILES = ('limits.json', 'humanoid_uefn.xml', 'physics.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_source():
    meta = json.loads((SOURCE / 'limits.json').read_text())
    rig_path = ROOT / meta['source_rig']
    assert sha(rig_path) == meta['source_sha256'], 'Regenerate model from current PHAT export'
    rig = json.loads(rig_path.read_text())
    for name, info in rig['source_files'].items():
        assert sha(ROOT / name) == info['sha256'], f'PHAT export is stale: {name}'
    incoming = {j['name']: j for j in rig['joints']}
    import numpy as np
    for j in meta['joints']:
        src = incoming[j['source_joint']]
        assert j['modes'] == src['angular_modes_twist_swing2_swing1']
        np.testing.assert_allclose(np.rad2deg(j['limits_rad']), src['angular_limits_deg_twist_swing2_swing1'], atol=1e-8)
    physics = json.loads((SOURCE / 'physics.json').read_text())
    assert physics['source_sha256'] == meta['source_sha256']
    assert physics['asset_sha256'] == sha(SOURCE / 'humanoid_uefn.xml')
    return meta


def verify_current_phat(asset):
    meta = current_source()
    for name in FILES:
        assert sha(asset / name) == sha(SOURCE / name), f'Crawl package differs from current PHAT: {name}'
    return meta


def sync_current_phat(asset):
    meta = current_source()
    old = json.loads((asset / 'limits.json').read_text())
    # A limit refresh cannot silently change the coordinate system or robot.
    for key in ('geometry', 'groups', 'body_frames', 'source_body_frames', 'source_parents', 'parents', 'mass_kg', 'collision_exclusions'):
        assert old[key] == meta[key], f'Geometry changed; explicit rebuild required: {key}'
    for a, b in zip(old['joints'], meta['joints']):
        for key in ('body', 'source_body', 'source_joint', 'kind', 'reference_wxyz'):
            assert a[key] == b[key], f'Joint frame changed: {a["body"]}/{key}'
    for name in FILES:
        shutil.copy2(SOURCE / name, asset / name)
    return verify_current_phat(asset)
