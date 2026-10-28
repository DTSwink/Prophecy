"""Reproduce alternate 5s fixtures used by verify-direction-phases.mjs and
verify-direction-release.mjs, through the FootIK service's one-thread worker.

From the repository root, with the existing API6+ FootIK server running:
  python -B Labs/FootIKLab/generate-direction-phases.py --url http://127.0.0.1:8890
Or check existing fixtures entirely offline, without inference or server access:
  python -B Labs/FootIKLab/generate-direction-phases.py --check-only

Use the project's Stepper Python if python is not on PATH. The default URL is
FOOTIK_DIRECTION_TEST_URL or http://127.0.0.1:8890. Requests are strictly serial;
this script never starts/stops a server or worker. Valid existing files are
retained byte-for-byte. Missing files alone are generated; --force explicitly
replaces all six. Invalid existing fixtures fail rather than silently changing
the inputs to a regression test. Output is confined to .nn-cache/.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import urllib.request

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
CASES = (
    ('walk', 'backward', .49),
    ('run', 'backward', .73),
    ('walk', 'left', 0),
    ('walk', 'right', 0),
    ('run', 'left', .49),
    ('run', 'right', .73),
)


def filename(gait, direction):
    return f'directional-phase-{gait}-{direction}.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_receipt():
    """Keep filenames, phases and duration aligned with the accepted capture."""
    path = ROOT/'directional-full-phase-generation.json'
    if not path.exists():
        return
    recorded = json.loads(path.read_text(encoding='utf-8'))['cases']
    expected = {(g, d): (p, filename(g, d)) for g, d, p in CASES}
    require(len(recorded) == len(expected), 'Capture receipt case count differs')
    for row in recorded:
        key = row['gait'], row['direction']
        name = row['path'].replace('\\', '/').rsplit('/', 1)[-1]
        require(key in expected and (row['phase'], name) == expected[key]
                and row['duration'] == 5, 'Capture receipt names/phases differ')
        del expected[key]
    require(not expected, 'Capture receipt omits a required phase')


def validate_sources(contract):
    for name in ('source', 'drawn'):
        item = contract[name]
        actual = hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()
        require(actual == item['sha256'], 'Immutable directional source changed: ' + item['path'])


def validate(data, gait, direction, phase, contract, names):
    label = gait + '/' + direction
    require(data.get('gait') == gait and data.get('direction') == direction
            and data.get('phase') == phase, label + ': wrong gait, direction or phase')
    require(data.get('duration') == 5 and data.get('fps') == 30
            and len(data.get('poses', [])) == 152 and len(data.get('roots', [])) == 152,
            label + ': expected complete 5s/152-frame rollout')
    require(data.get('names') == names, label + ': bone order differs from lab rig')
    command = data.get('command', {})
    require(command.get('direction') == direction and command.get('relative') == contract['relative']
            and command.get('sourceSha256') == contract['source']['sha256']
            and command.get('drawnSha256') == contract['drawn']['sha256'], label + ': source hash/context differs')
    require(data.get('lowerInferences', 0) >= 211 and data.get('upperInferences', 0) >= 150
            and 'autoregressive' in data.get('source', ''), label + ': not a complete genuine NN rollout')
    for root, pose in zip(data['roots'], data['poses']):
        require(len(root) == 3 and all(math.isfinite(x) for x in root), label + ': invalid root')
        require(len(pose['points']) == len(names) and len(pose['axes']) == len(names), label + ': incomplete body')
        for point, axes in zip(pose['points'], pose['axes']):
            require(len(point) == 3 and all(math.isfinite(x) for x in point), label + ': invalid joint position')
            require(len(axes) == 3 and all(len(axis) == 3 and all(math.isfinite(x) for x in axis) for axis in axes),
                    label + ': invalid joint axes')


def fetch(url, request=None):
    body = None if request is None else json.dumps(request, allow_nan=False).encode('utf-8')
    http = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(http, timeout=60) as response:
        result = json.loads(response.read())
    if 'error' in result:
        raise RuntimeError(result['error'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--url', default=os.environ.get('FOOTIK_DIRECTION_TEST_URL', 'http://127.0.0.1:8890'))
    parser.add_argument('--check-only', action='store_true', help='Validate existing fixtures without any network access')
    parser.add_argument('--force', action='store_true', help='Explicitly regenerate all six fixtures serially')
    args = parser.parse_args()
    require(not (args.check_only and args.force), '--check-only and --force are mutually exclusive')
    endpoint = args.url.rstrip('/')
    manifest = json.loads((ROOT/'directional-sources.json').read_text(encoding='utf-8'))
    names = json.loads((ROOT/'data/rig.json').read_text(encoding='utf-8'))['names'][1:]
    validate_receipt()
    checked_server = False
    generated = 0
    for gait, direction, phase in CASES:
        contract = manifest['sources'][gait][direction]
        validate_sources(contract)
        path = ROOT/'.nn-cache'/filename(gait, direction)
        if path.exists() and not args.force:
            data = json.loads(path.read_text(encoding='utf-8'))
            validate(data, gait, direction, phase, contract, names)
            status = 'retained'
        else:
            require(not args.check_only, 'Missing fixture: ' + str(path))
            if not checked_server:
                health = fetch(endpoint+'/health')
                require(health.get('app') == 'foot-ik-lab' and health.get('apiVersion', 0) >= 6
                        and Path(health.get('root', '')).resolve() == ROOT, 'URL is not this FootIK API6+ server')
                checked_server = True
            data = fetch(endpoint+'/run', dict(gait=gait, direction=direction, duration=5, phase=phase))
            validate(data, gait, direction, phase, contract, names)
            path.parent.mkdir(exist_ok=True)
            temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
            try:
                temporary.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False), encoding='utf-8')
                temporary.replace(path)
            finally:
                if temporary.exists():
                    temporary.unlink()
            generated += 1
            status = 'generated'
        print(json.dumps(dict(gait=gait, direction=direction, phase=phase, status=status,
            file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())), flush=True)
    print(json.dumps(dict(validated=len(CASES), generated=generated, retained=len(CASES)-generated)), flush=True)


if __name__ == '__main__':
    main()
