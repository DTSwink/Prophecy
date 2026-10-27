"""Read-only extraction of the Final Harness's original, unretargeted clips."""
import base64
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = Path(r'C:\Users\singerie\Documents\Cursor\stepper\training\slashes2\final_harness_standalone\index.html')


def main():
    import numpy as np
    text = SOURCE.read_text(encoding='utf-8')
    match = re.search(r'const basePayload\s*=\s*', text)
    payload, _ = json.JSONDecoder().raw_decode(text[match.end():])
    rig = json.loads((ROOT / 'data/manifest.json').read_text())
    assert payload['bone_names'] == rig['names'] and payload['parents'] == rig['parents']
    folder = ROOT / 'data/vanilla'
    folder.mkdir(exist_ok=True)
    clips = []
    for clip in payload['clips']:
        source = Path(clip['source_npz'])
        with np.load(source, allow_pickle=False) as data:
            phases = {key: float(data['attack_' + key + '_frame']) for key in ('armed', 'hit')}
            points = base64.b64decode(clip['positions_b64'])
            basis = base64.b64decode(clip['basis_b64'])
            assert len(points) + len(basis) == clip['frame_count'] * len(rig['names']) * 48
            raw = points + basis
            (folder / (clip['name'] + '.bin')).write_bytes(raw)
            clips.append(dict(name=clip['name'], file='data/vanilla/' + clip['name'] + '.bin',
                              frames=clip['frame_count'], fps=clip['fps'], phases=phases,
                              source=str(source), sha256=hashlib.sha256(raw).hexdigest()))
    receipt = dict(schema=1, source=str(SOURCE), sourceSHA256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                   contract='Original basePayload positions/basis, before target solvers; Armed/Hit from source NPZ.',
                   clips=clips)
    (ROOT / 'data/vanilla.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(f'Extracted {len(clips)} vanilla attacks, {sum(c["frames"] for c in clips)} frames.')


if __name__ == '__main__':
    main()
