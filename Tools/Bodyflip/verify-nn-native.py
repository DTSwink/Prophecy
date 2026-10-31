"""Emit original-PyTorch fixtures and compare bounded native NNE rollouts.

Uses one CPU thread through the existing lab loader. Never contacts Unreal,
changes a scene, or alters the active manager. Native automation writes the
request/actual files consumed here after the coordinated build.
"""
import argparse
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / 'Labs/BodyflipLab'))
from resume_locomotion import ResumeLocomotion
from locomotion import torch

FOLDER = PROJECT / 'Saved/Diagnostics/BodyflipPort20261030/NN'


def request_from_bank(stem):
    bank = json.loads((PROJECT / 'Content/BodyflipLab/NN' / (stem + '-seeds.json')).read_text())
    pair = bank['phases'][round(.5 * bank['stride'])]
    previous, current = torch.tensor(pair['roots'], dtype=torch.float32)
    roots = torch.stack([current + i * (current - previous) for i in range(-1, 24)])
    seeds = [dict(points=[root.tolist(), *pose['points']],
                  axes=[torch.eye(3).tolist(), *pose['axes']])
             for root, pose in zip(roots[:2], pair['seeds'])]
    return dict(gait=stem.split('-')[0], drawn=stem.endswith('-drawn'), names=['root', *bank['names']],
                roots=roots.tolist(), seeds=seeds, frames=16, time=0)


def errors(actual, expected):
    if len(actual['poses']) != len(expected['poses']) or actual['names'] != expected['names']:
        raise AssertionError('Native frame count or bone order differs')
    result = {}
    for field in ('points', 'axes'):
        a = torch.tensor([p[field] for p in actual['poses']], dtype=torch.float64)
        b = torch.tensor([p[field] for p in expected['poses']], dtype=torch.float64)
        result[field] = float((a-b).abs().max())
    for field in ('roots', 'seedLower', 'seedUpper'):
        result[field] = float((torch.tensor(actual[field], dtype=torch.float64)
                              - torch.tensor(expected[field], dtype=torch.float64)).abs().max())
    result['continuation'] = max(float((torch.tensor(actual['continuation'][key], dtype=torch.float64)
                                       - torch.tensor(value, dtype=torch.float64)).abs().max())
                                 for key, value in expected['continuation'].items())
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profiles', default='run-unarmed,run-drawn,walk-unarmed,walk-drawn')
    parser.add_argument('--require-native', action='store_true')
    parser.add_argument('--tolerance', type=float, default=5e-4)
    parser.add_argument('--folder', type=Path, default=FOLDER,
                        help='Native host NN receipt directory; keeps isolated runs in place')
    args = parser.parse_args()
    args.folder.mkdir(parents=True, exist_ok=True)
    owner = None
    reports = []
    for stem in args.profiles.split(','):
        gait = stem.split('-')[0]
        if owner is None or owner.gait != gait:
            owner = ResumeLocomotion(gait)
        native_path = args.folder / (stem + '-native.json')
        native = json.loads(native_path.read_text(encoding='utf-8-sig')) if native_path.exists() else None
        if args.require_native and native is None:
            raise FileNotFoundError(native_path)
        request = native['request'] if native else request_from_bank(stem)
        expected = owner.resume(request)
        (args.folder / (stem + '-fixture.json')).write_text(json.dumps(dict(request=request, expected=expected), separators=(',', ':')))
        report = dict(profile=stem, frames=len(expected['poses']), nativeCompared=native is not None)
        if native:
            report['errors'] = errors(native['actual'], expected)
            if max(report['errors'].values()) > args.tolerance:
                raise AssertionError(json.dumps(report))
        reports.append(report)
        print(json.dumps(report), flush=True)
    (args.folder / 'python-parity.json').write_text(json.dumps(dict(tolerance=args.tolerance, profiles=reports), indent=2))


if __name__ == '__main__':
    main()
