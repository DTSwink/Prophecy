"""Paired contact-rule audit on the unchanged, accepted 100 Get Up starts.

Runs isolated Jolt processes; never loads or changes the interactive editor.
Uses the original terminal rules, stopping on first success/failure/timeout.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import time

from AuditTransfer import Jolt, OUT, ROOT, ref
import numpy as np

sys.path.insert(0, str(ROOT / 'Labs/MimicKitTransfer'))
import getup_transfer as original


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inference', choices=['torch', 'onnx'], default='torch')
    parser.add_argument('--count', type=int, default=100)
    args = parser.parse_args()
    source = original.OUT / 'fresh-100'
    starts = np.load(source / 'starts.npz')
    manifest = json.loads((source / 'manifest.json').read_text())
    native = json.loads((source / 'native.json').read_text())
    policy = original.Policy('native') if args.inference == 'torch' else None
    os.environ['AUDIT_FIXTURE'] = str(OUT / 'point/fixture.exe')
    os.environ['AUDIT_DLL_DIR'] = str(ROOT / 'Saved/MimicKitTransfer/no-armature-3913/point-contact')
    results = []
    started = time.perf_counter()
    for case, row in enumerate(manifest['rows'][:args.count]):
        for rule in ('manifold', 'point'):
            flags = {'CAND_SPHERICAL': '1', 'CAND_LIMIT_HZ': '32',
                     'AUDIT_MANIFOLD': '1' if rule == 'manifold' else None}
            sim = Jolt(starts['states'][case], flags)
            state = sim.state
            phase = starts['phase'][case].copy()
            history = [state]
            try:
                for tick in range(1, row['getup_max_ticks'] + 1):
                    obs = original.observation(state, row, phase)
                    action, following = (policy(obs) if policy else
                        ref.policies[0].run(None, {'observations': obs.numpy()}))
                    phase = following[0]
                    state = sim.step(action[0])
                    assert np.isfinite(state).all()
                    history.append(state)
                    terminal = original.outcome(state, tick, row)
                    if terminal:
                        break
            finally:
                sim.close()
            item = dict(case=case, rule=rule, inference=args.inference,
                        terminal=terminal, ticks=tick,
                        head_m=float(state[2, 2]), pelvis_m=float(state[0, 2]),
                        native_terminal=native[case]['terminal'],
                        cohort=('front' if 'front' in row['recovery_motion_file'].lower() else 'back')
                            + ('_plus' if row['perturbed_plus_row'] else '_ordinary'))
            history = np.asarray(history)
            if rule == 'manifold' and args.inference == 'torch':
                saved = np.load(source / f'unreal-{case:03d}.npz')['states']
                common = min(len(saved), len(history))
                item['historical_exact'] = np.array_equal(saved, history)
                item['historical_max_abs_error'] = float(np.max(abs(saved[:common] - history[:common])))
                item['historical_ticks'] = len(saved) - 1
            if terminal != 2:
                np.savez_compressed(OUT / f'getup-{args.inference}-{rule}-{case:03d}.npz', states=history)
            results.append(item)
        if case % 10 == 9 or case == args.count - 1:
            print(json.dumps(dict(inference=args.inference, completed=case + 1,
                successes={rule: sum(r['terminal'] == 2 for r in results if r['rule'] == rule)
                           for rule in ('manifold', 'point')}, elapsed_s=round(time.perf_counter()-started, 1))), flush=True)
            (OUT / f'getup-{args.inference}.json').write_text(json.dumps(results, indent=2))
    by_rule = {rule: [r for r in results if r['rule'] == rule] for rule in ('manifold', 'point')}
    summary = dict(inference=args.inference, count=args.count, seed=manifest['seed'],
        starts_sha256=hashlib.sha256((source / 'starts.npz').read_bytes()).hexdigest(),
        native_successes=sum(r['terminal'] == 2 for r in native[:args.count]),
        rules={}, regressions=[], improvements=[],
        scope='Isolated Jolt; same initial poses, velocities, phase, weights, spherical32 limits; original first terminal rules; editor unchanged')
    for rule, rows in by_rule.items():
        summary['rules'][rule] = dict(successes=sum(r['terminal'] == 2 for r in rows),
            native_success_transfer=sum(r['terminal'] == r['native_terminal'] == 2 for r in rows),
            failures=[r['case'] for r in rows if r['terminal'] != 2],
            median_ticks=float(np.median([r['ticks'] for r in rows if r['terminal'] == 2])),
            cohorts={cohort: sum(r['terminal'] == 2 for r in rows if r['cohort'] == cohort)
                     for cohort in sorted({r['cohort'] for r in rows})})
    for old, new in zip(by_rule['manifold'], by_rule['point']):
        if old['terminal'] == 2 and new['terminal'] != 2:
            summary['regressions'].append(new['case'])
        if old['terminal'] != 2 and new['terminal'] == 2:
            summary['improvements'].append(new['case'])
    if args.inference == 'torch':
        summary['historical_exact_count'] = sum(r['historical_exact'] for r in by_rule['manifold'])
        summary['historical_max_abs_error'] = max(r['historical_max_abs_error'] for r in by_rule['manifold'])
    summary['elapsed_s'] = time.perf_counter() - started
    (OUT / f'getup-{args.inference}-summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
