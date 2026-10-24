"""Read precomputed exact NN phase rollouts; no torch or worker in the server."""
import json, math, struct
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'data'

@lru_cache(maxsize=4)
def metadata(gait, drawn):
    stem = gait + ('-drawn' if drawn else '') + '-phases'
    return stem, json.loads((ROOT / (stem + '.json')).read_text(encoding='utf-8'))

def read_run(gait, duration, phase, drawn):
    stem, meta = metadata(gait, drawn)
    slot = round((phase % 1) * meta['stride'])
    count = math.ceil(duration * meta['fps']) + 2
    width = 3 + len(meta['names']) * 12
    if count > meta['framesPerPhase']:
        raise ValueError('Requested duration exceeds cached rollout')
    with (ROOT / (stem + '.bin')).open('rb') as f:
        f.seek(slot * meta['framesPerPhase'] * width * 4)
        raw = f.read(count * width * 4)
    poses, roots = [], []
    for row in struct.iter_unpack('<' + str(width) + 'f', raw):
        roots.append(row[:3])
        points, axes = [], []
        for j in range(len(meta['names'])):
            k = 3 + j * 12
            points.append(row[k:k+3])
            axes.append([row[k+3:k+6], row[k+6:k+9], row[k+9:k+12]])
        poses.append(dict(points=points, axes=axes))
    return dict(meta, duration=duration, phase=phase, poses=poses, roots=roots,
                cache='phase-bank-v1', seconds=0, upperInferences=0)
