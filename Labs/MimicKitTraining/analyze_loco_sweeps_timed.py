"""Compare real snapshots at different sample counts, retaining paired checks.

Default: compare each result's first PPO update crossing its timed target.
  python analyze_loco_sweeps_timed.py CANDIDATE.json BASELINE.json
Or select two explicit recorded endpoints (no interpolation):
  python analyze_loco_sweeps_timed.py CANDIDATE.json BASELINE.json --candidate-update 1200 --baseline-update 1024
"""
import argparse
import json
import math
from pathlib import Path

from analyze_loco_sweeps import compare, index_evaluations, training_summary


def endpoint_readiness(candidate, baseline, candidate_update, baseline_update):
    """A complete paired evaluation requires the entire planned seed set."""
    details, reasons = {}, []
    for label, result, endpoint in (('candidate', candidate, candidate_update),
                                    ('baseline', baseline, baseline_update)):
        actual = sorted(index_evaluations(result, endpoint))
        expected = result.get('evaluation_seeds')
        valid_plan = (isinstance(expected, list) and len(expected) >= 8
                      and all(isinstance(seed, int) and not isinstance(seed, bool) for seed in expected)
                      and len(set(expected)) == len(expected))
        details[label] = dict(complete=result.get('complete'), failed=result.get('failed'),
            equivalent_updates=endpoint, actual_seeds=actual,
            expected_seeds=sorted(expected) if valid_plan else expected,
            missing_seeds=sorted(set(expected)-set(actual)) if valid_plan else None,
            unexpected_seeds=sorted(set(actual)-set(expected)) if valid_plan else None)
        if result.get('failed'):
            reasons.append(label + '_failed')
        elif not result.get('complete'):
            reasons.append(label + '_in_progress')
        if not valid_plan:
            reasons.append(label + '_invalid_planned_evaluation_seeds')
        elif set(actual) != set(expected):
            reasons.append(label + '_evaluation_seed_set_incomplete_or_unexpected')
    return dict(ready=not reasons, reasons=reasons, endpoint_details=details)


def compare_endpoints(candidate, baseline, candidate_update, baseline_update,
                      repetitions=2000, bootstrap_seed=94721):
    """Relabel only selected evaluations, then restore each actual training total."""
    readiness = endpoint_readiness(candidate, baseline, candidate_update, baseline_update)
    selected = []
    for result, endpoint in ((candidate, candidate_update), (baseline, baseline_update)):
        # The existing comparator expects a common endpoint label. No state or
        # start hashes change, and original input objects remain untouched.
        view = dict(result)
        view['evaluations'] = [dict(entry, evaluation_update=0)
            for entry in index_evaluations(result, endpoint).values()]
        selected.append(view)
    output = compare(*selected, 0, repetitions=repetitions, bootstrap_seed=bootstrap_seed)
    output.update(comparison_basis='explicit_recorded_endpoints',
        equivalent_updates=candidate_update if candidate_update == baseline_update else None,
        candidate_equivalent_updates=candidate_update, baseline_equivalent_updates=baseline_update,
        candidate_training=training_summary(candidate, candidate_update),
        baseline_training=training_summary(baseline, baseline_update), interpolation_used=False,
        readiness=readiness)
    for side in ('candidate', 'baseline'):
        if not output[side + '_training']['exact_update_available']:
            output['errors'].append(side + ': exact training update is missing')
    output['errors'].extend('Not ready: ' + reason for reason in readiness['reasons'])
    output['paired_valid'] = not output['errors']
    if not output['paired_valid']:
        # A few matching seeds must never appear to be a completed experiment.
        output['groups'] = {}
    return output


def timed_endpoint(result):
    """Validate that this snapshot is the first update crossing measured time."""
    timing = result.get('timed_training', {})
    receipt = timing.get('snapshot')
    if not timing.get('reached') or not isinstance(receipt, dict):
        raise ValueError('Timed target was not reached; no equal-time snapshot exists')
    endpoint = receipt.get('equivalent_updates')
    summary = training_summary(result, endpoint)
    if not summary['exact_update_available']:
        raise ValueError('Timed snapshot has no matching exact training update')
    rows = [row for row in result.get('updates', []) if row['equivalent_updates'] <= endpoint]
    if not rows:
        raise ValueError('Timed snapshot cannot refer to the untrained checkpoint')
    target = timing.get('target_seconds')
    if not isinstance(target, (int, float)) or not math.isfinite(target) or target <= 0:
        raise ValueError('Invalid timed target')
    durations = [row.get('seconds') for row in rows]
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in durations):
        raise ValueError('Invalid measured PPO-update durations')
    actual, previous = sum(durations), sum(durations[:-1])
    if not previous < target <= actual:
        raise ValueError('Timed snapshot is not the first update crossing the target')
    for field, expected in (('target_seconds', target), ('actual_training_seconds', actual),
                            ('previous_training_seconds', previous),
                            ('crossing_update_seconds', durations[-1]),
                            ('overshoot_seconds', actual-target),
                            ('actual_training_updates', len(rows)),
                            ('transitions', rows[-1]['transitions'])):
        found = receipt.get(field)
        if not isinstance(found, (int, float)) or not math.isclose(found, expected, rel_tol=1e-10, abs_tol=1e-7):
            raise ValueError('Timed receipt disagrees with actual update history: ' + field)
    if rows[-1].get('update') != len(rows):
        raise ValueError('Timed update count is inconsistent')
    if 'training_wall_seconds' in receipt:
        wall = receipt['training_wall_seconds']
        if not isinstance(wall, (int, float)) or not math.isfinite(wall) or wall < actual-1e-7:
            raise ValueError('Timed training wall time is smaller than summed update time')
    return endpoint, dict(receipt)


def compare_timed(candidate, baseline, repetitions=2000, bootstrap_seed=94721):
    candidate_update, candidate_receipt = timed_endpoint(candidate)
    baseline_update, baseline_receipt = timed_endpoint(baseline)
    if candidate_receipt['target_seconds'] != baseline_receipt['target_seconds']:
        raise ValueError('Equal-time comparison requires the same requested training seconds')
    output = compare_endpoints(candidate, baseline, candidate_update, baseline_update,
                               repetitions, bootstrap_seed)
    output.update(comparison_basis='first_completed_update_crossing_equal_training_time',
        target_training_seconds=candidate_receipt['target_seconds'],
        timing_scope='completed PPO updates only; excludes initialization, diagnostics, snapshots and evaluation',
        time_tolerance='at most the crossing PPO update for each variant',
        candidate_timed_snapshot=candidate_receipt, baseline_timed_snapshot=baseline_receipt,
        actual_training_time_difference_seconds=candidate_receipt['actual_training_seconds']-
            baseline_receipt['actual_training_seconds'])
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate')
    parser.add_argument('baseline')
    parser.add_argument('--candidate-update', type=int)
    parser.add_argument('--baseline-update', type=int)
    parser.add_argument('--bootstrap-repetitions', type=int, default=2000)
    parser.add_argument('--output')
    args = parser.parse_args()
    candidate = json.loads(Path(args.candidate).read_text())
    baseline = json.loads(Path(args.baseline).read_text())
    if (args.candidate_update is None) != (args.baseline_update is None):
        parser.error('Specify both explicit endpoints, or neither for timed snapshots')
    if args.candidate_update is None:
        output = compare_timed(candidate, baseline, args.bootstrap_repetitions)
    else:
        output = compare_endpoints(candidate, baseline, args.candidate_update,
                                   args.baseline_update, args.bootstrap_repetitions)
    encoded = json.dumps(output, indent=2, allow_nan=False)
    if args.output:
        Path(args.output).write_text(encoded)
    else:
        print(encoded)


if __name__ == '__main__':
    main()
