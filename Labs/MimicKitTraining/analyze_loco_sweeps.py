"""Analyze isolated loco_learning_sweep results without cloud or GPU access.

Example: python analyze_loco_sweeps.py LOCAL_DIRECTORY --baseline baseline
Negative failure-rate differences favor the candidate. Bootstrap intervals cover
evaluation sampling only, NOT variability between independent training seeds.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np


GROUPS = {'normal_loco': (0,), 'perturbed_loco': (1,), 'idle': (2, 3)}
ORDER_FIELDS = ('row_ids', 'motion_id', 'group', 'gait', 'equipment', 'initial_yaw_degrees')
METRICS = ('actor_learning_rate', 'policy_kl', 'clip_frac', 'actor_steps_accepted',
           'actor_steps_rejected', 'actor_full_rollback', 'critic_explained_variance',
           'critic_loss', 'critic_mse_after_update', 'critic_target_variance')
EVAL_METRICS = ('end_ticks', 'episode_return', 'mean_body_tracking_cost',
                'mean_body_position_distance_m2', 'end_body_position_distance_m2')


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def stats(values):
    values = np.asarray([v for v in values if finite(v)], dtype=float)
    if not len(values):
        return None
    return dict(count=len(values), mean=float(values.mean()), median=float(np.median(values)),
                minimum=float(values.min()), maximum=float(values.max()), last=float(values[-1]))


def index_evaluations(result, update):
    found = {}
    for entry in result.get('evaluations', []):
        if entry.get('evaluation_update') == update:
            seed = entry.get('seed')
            if seed in found:
                raise ValueError(f"Duplicate evaluation seed {seed} at update {update}")
            found[seed] = entry
    return found


def world_counts(result):
    """Older runner used worlds for both; newer results declare each explicitly."""
    training = result.get('training_worlds', result.get('worlds'))
    evaluation = result.get('evaluation_worlds', result.get('worlds'))
    return training, evaluation


def training_initialization_check(candidate, baseline):
    cw, _ = world_counts(candidate)
    bw, _ = world_counts(baseline)
    cs, bs = candidate.get('training_seed'), baseline.get('training_seed')
    details = dict(candidate_worlds=cw, baseline_worlds=bw, candidate_seed=cs, baseline_seed=bs,
                   applicable=False, matching=None, errors=[])
    if cw is None or bw is None or cs is None or bs is None:
        details['reason'] = 'Training worlds or seed missing; hash comparison unavailable'
    elif cw != bw or cs != bs:
        details['reason'] = 'Different training world count or seed; only held-out evaluation starts are paired'
    else:
        details['applicable'] = True
        details['reason'] = 'Same training world count and seed'
        hashes = []
        for label, result in (('candidate', candidate), ('baseline', baseline)):
            value = result.get('training_initial_hashes')
            if not isinstance(value, dict) or not all(value.get(k) for k in
                    ('observation', 'position', 'velocity', 'target', 'motion', 'yaw')):
                details['errors'].append(label + ': missing or incomplete training_initial_hashes')
            recorded = result.get('training_initial_hashes_worlds')
            if recorded is not None and recorded != world_counts(result)[0]:
                details['errors'].append(label + ': training hash world count differs from declared training_worlds')
            hashes.append(value)
        if not details['errors']:
            details['matching'] = hashes[0] == hashes[1]
            if not details['matching']:
                details['errors'].append('training_initial_hashes differ for matching training worlds and seed')
    return details


def training_summary(result, update):
    rows = [r for r in result.get('updates', []) if finite(r.get('equivalent_updates'))
            and r['equivalent_updates'] <= update]
    exact = update == 0 or any(r['equivalent_updates'] == update for r in rows)
    durations = [r.get('seconds') for r in rows]
    seconds = sum(durations) if exact and all(finite(v) for v in durations) else None
    transitions = rows[-1].get('transitions') if rows and exact else (0 if update == 0 else None)
    diagnostics = {key: stats([r.get('metrics', {}).get(key) for r in rows]) for key in METRICS}
    tail = {key: stats([r.get('metrics', {}).get(key) for r in rows[-32:]]) for key in METRICS}
    training_worlds, evaluation_worlds = world_counts(result)
    return dict(equivalent_updates=update, exact_update_available=exact,
                training_worlds=training_worlds, evaluation_worlds=evaluation_worlds,
                cumulative_update_seconds=seconds, transitions=transitions,
                transitions_per_update_second=(transitions / seconds if seconds and transitions else None),
                update_count=len(rows), initial_actor_lr=result.get('actual_actor_lr'),
                initial_critic_lr=result.get('actual_critic_lr'), diagnostics=diagnostics,
                final_32_updates_diagnostics=tail,
                rejected_actor_steps_sum=sum(r['metrics']['actor_steps_rejected'] for r in rows)
                if rows and all(finite(r.get('metrics', {}).get('actor_steps_rejected')) for r in rows) else None,
                full_rollbacks_sum=sum(r['metrics']['actor_full_rollback'] for r in rows)
                if rows and all(finite(r.get('metrics', {}).get('actor_full_rollback')) for r in rows) else None)


def check_entry(entry):
    count = entry.get('rows')
    errors = []
    if not isinstance(count, int) or count <= 0:
        return ['Missing or invalid rows count']
    for key in ORDER_FIELDS + ('final_done',):
        if not isinstance(entry.get(key), list) or len(entry[key]) != count:
            errors.append(f'{key}: missing or wrong row count')
    hashes = entry.get('initial_hashes')
    if not isinstance(hashes, dict) or not hashes or any(not v for v in hashes.values()):
        errors.append('Missing initial_hashes')
    elif not all(key in hashes for key in ('observation', 'position', 'velocity', 'target', 'motion', 'yaw')):
        errors.append('Incomplete initial_hashes')
    if entry.get('group_labels') != {'0': 'normal_loco', '1': 'perturbed_loco',
                                    '2': 'normal_idle', '3': 'perturbed_idle'}:
        errors.append('Missing or unsupported group_labels')
    if isinstance(entry.get('row_ids'), list) and len(set(entry['row_ids'])) != count:
        errors.append('row_ids are not unique')
    return errors


def group_summary(entries, codes):
    failures = count = unfinished = 0
    values = {k: [] for k in EVAL_METRICS}
    missing = {k: [] for k in EVAL_METRICS}
    for seed, entry in entries.items():
        if check_entry(entry):
            continue
        ids = [i for i, g in enumerate(entry['group']) if g in codes]
        count += len(ids)
        failures += sum(entry['final_done'][i] == 1 for i in ids)
        unfinished += sum(entry['final_done'][i] == 0 for i in ids)
        for key in values:
            raw = entry.get(key)
            if not isinstance(raw, list) or len(raw) != entry['rows'] or any(not finite(raw[i]) for i in ids):
                missing[key].append(seed)
            else:
                values[key].extend(raw[i] for i in ids)
    summary = dict(rows=count, failures=failures, unfinished=unfinished,
                   failure_percent=100 * failures / count if count else None,
                   seeds=len(entries), metrics={k: (stats(v) if not missing[k] else None)
                   for k, v in values.items()}, missing_metric_seeds={k: v for k, v in missing.items() if v})
    for key in ('mean_body_position_distance_m2', 'end_body_position_distance_m2'):
        item = summary['metrics'][key]
        summary[key.replace('distance_m2', 'rms_cm')] = 100 * math.sqrt(item['mean']) if item and item['mean'] >= 0 else None
    return summary


def paired_interval(differences, repetitions, seed):
    """Hierarchical paired bootstrap: seeds, then rows within selected seeds."""
    if len(differences) < 2 or repetitions < 2:
        return None
    rng = np.random.default_rng(seed)
    samples = np.empty(repetitions)
    for repeat in range(repetitions):
        total = count = 0
        for selected in rng.integers(0, len(differences), len(differences)):
            row = differences[selected]
            drawn = row[rng.integers(0, len(row), len(row))]
            total += drawn.sum()
            count += len(drawn)
        samples[repeat] = 100 * total / count
    return [float(x) for x in np.quantile(samples, [.025, .975])]


def compare(candidate, baseline, update, repetitions=2000, bootstrap_seed=94721):
    c = index_evaluations(candidate, update)
    b = index_evaluations(baseline, update)
    seeds = sorted(set(c) & set(b))
    errors = []
    train_start_check = training_initialization_check(candidate, baseline)
    errors.extend(train_start_check['errors'])
    _, candidate_eval_worlds = world_counts(candidate)
    _, baseline_eval_worlds = world_counts(baseline)
    if candidate_eval_worlds is not None and baseline_eval_worlds is not None and candidate_eval_worlds != baseline_eval_worlds:
        errors.append('Declared evaluation_worlds differ')
    for field in ('checkpoint_sha256', 'environment_config_sha256', 'motion_names'):
        if not candidate.get(field) or not baseline.get(field):
            errors.append(f'Missing {field}')
        elif candidate[field] != baseline[field]:
            errors.append(f'{field} differs')
    for seed in seeds:
        for side, entries in (('candidate', c), ('baseline', b)):
            errors.extend(f'{side} seed {seed}: {e}' for e in check_entry(entries[seed]))
            declared_worlds = candidate_eval_worlds if side == 'candidate' else baseline_eval_worlds
            if declared_worlds is not None and entries[seed].get('rows') != declared_worlds:
                errors.append(f'{side} seed {seed}: rows differ from declared evaluation_worlds')
        if c[seed].get('initial_hashes') != b[seed].get('initial_hashes'):
            errors.append(f'seed {seed}: initial_hashes differ')
        for field in ORDER_FIELDS:
            if c[seed].get(field) != b[seed].get(field):
                errors.append(f'seed {seed}: {field} ordering or values differ')
        if c[seed].get('group_labels') != b[seed].get('group_labels'):
            errors.append(f'seed {seed}: group_labels differ')
    if not seeds:
        errors.append('No matching evaluation seeds at this update')
    output = dict(candidate=candidate.get('variant'), baseline=baseline.get('variant'),
                  equivalent_updates=update, candidate_training=training_summary(candidate, update),
                  baseline_training=training_summary(baseline, update), paired_valid=not errors,
                  errors=errors, matching_seeds=seeds,
                  training_initialization_check=train_start_check,
                  evaluation_worlds=dict(candidate=candidate_eval_worlds, baseline=baseline_eval_worlds),
                  candidate_only_seeds=sorted(set(c) - set(b)), baseline_only_seeds=sorted(set(b) - set(c)),
                  groups={})
    if errors:
        return output
    for name, codes in GROUPS.items():
        # Screening may stop six seeds at120ticks. Normal episodes need300;
        # never turn their censored observations into apparent non-failures.
        # Combined idle includes normal rows, so use full-horizon seeds there.
        group_seeds = seeds if name == 'perturbed_loco' else [s for s in seeds
            if c[s].get('full_normal_horizon', True) and b[s].get('full_normal_horizon', True)]
        cs = group_summary({s: c[s] for s in group_seeds}, codes)
        bs = group_summary({s: b[s] for s in group_seeds}, codes)
        diffs, improved, worsened = [], 0, 0
        for s in group_seeds:
            ids = [i for i, g in enumerate(c[s]['group']) if g in codes]
            if not ids:
                continue
            cf = np.asarray([c[s]['final_done'][i] == 1 for i in ids], dtype=np.int8)
            bf = np.asarray([b[s]['final_done'][i] == 1 for i in ids], dtype=np.int8)
            diffs.append(cf - bf)
            improved += int(((cf == 0) & (bf == 1)).sum())
            worsened += int(((cf == 1) & (bf == 0)).sum())
        difference = cs['failure_percent'] - bs['failure_percent'] if cs['rows'] else None
        metric_deltas = {}
        for key in EVAL_METRICS:
            cm, bm = cs['metrics'][key], bs['metrics'][key]
            metric_deltas[key] = (dict(candidate_mean=cm['mean'], baseline_mean=bm['mean'],
                difference=cm['mean'] - bm['mean'], ratio=cm['mean'] / bm['mean'] if bm['mean'] else None)
                if cm and bm else None)
        ci = paired_interval(diffs, repetitions, bootstrap_seed) if diffs else None
        output['groups'][name] = dict(candidate=cs, baseline=bs, failure_difference_pp=difference,
            matching_seeds=group_seeds, censored_seeds_excluded=sorted(set(seeds) - set(group_seeds)),
            paired_bootstrap_95ci_pp=ci, improved_rows=improved, worsened_rows=worsened,
            paired_metric_changes=metric_deltas,
            screening_flags=dict(failure_rate_higher=difference > 0 if difference is not None else None,
                failure_ci_excludes_zero_worse=ci[0] > 0 if ci else None,
                mean_tracking_cost_higher=metric_deltas['mean_body_tracking_cost']['difference'] > 0
                if metric_deltas['mean_body_tracking_cost'] else None,
                mean_end_tick_lower=metric_deltas['end_ticks']['difference'] < 0 if metric_deltas['end_ticks'] else None,
                end_position_error_higher=metric_deltas['end_body_position_distance_m2']['difference'] > 0
                if metric_deltas['end_body_position_distance_m2'] else None))
    return output


def format_number(value, digits=2):
    return f'{value:.{digits}f}' if finite(value) else 'missing'


def comparison_readiness(candidate, baseline, update):
    """Missing/pending data is not a failed pairing validation."""
    details = {}
    reasons = []
    for label, result in (('candidate', candidate), ('baseline', baseline)):
        entries = index_evaluations(result, update)
        planned = result.get('settings', {}).get('evaluate_at_updates')
        expected = result.get('evaluation_seeds')
        details[label] = dict(complete=result.get('complete'), failed=result.get('failed'),
            actual_seeds=sorted(entries), planned_evaluation_updates=planned,
            missing_seeds=sorted(set(expected) - set(entries)) if isinstance(expected, list) else None)
        if not result.get('complete'):
            reasons.append(label + ('_failed' if result.get('failed') else '_in_progress'))
        if not entries:
            reasons.append(label + ('_endpoint_not_planned' if isinstance(planned, list) and update not in planned
                                    else '_evaluation_missing'))
        elif isinstance(expected, list) and set(entries) != set(expected):
            reasons.append(label + '_evaluation_seed_set_incomplete')
    return dict(ready=not reasons, reasons=reasons, endpoint_details=details)


def render_table(report):
    lines = ['Failure difference = candidate minus baseline; negative favors candidate.',
        '95% intervals reflect evaluation uncertainty only, not training-seed variability.',
        'Time is cumulative measured update time; initialization/evaluation excluded.', '',
        '| Variant | Eq.updates | Train s | Perturbed failure % | Difference pp [95% CI] | Normal failure delta pp | Normal tracking ratio | End tick delta |',
        '|---|---:|---:|---:|---|---:|---:|---:|']
    for row in report['comparisons']:
        if not row['paired_valid']:
            lines.append(f"| {row['candidate']} | {row['equivalent_updates']} | — | INVALID PAIR | {'; '.join(row['errors'])} | — | — | — |")
            continue
        p, n = row['groups']['perturbed_loco'], row['groups']['normal_loco']
        ci = p['paired_bootstrap_95ci_pp']
        interval = f"[{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else '[missing]'
        ratio = n['paired_metric_changes']['mean_body_tracking_cost']
        end = p['paired_metric_changes']['end_ticks']
        lines.append(f"| {row['candidate']} | {row['equivalent_updates']} | {format_number(row['candidate_training']['cumulative_update_seconds'], 1)} | "
            f"{format_number(p['candidate']['failure_percent'])} | {format_number(p['failure_difference_pp'])} {interval} | "
            f"{format_number(n['failure_difference_pp'])} | {format_number(ratio['ratio'] if ratio else None, 3)} | "
            f"{format_number(end['difference'] if end else None)} |")
    lines.extend(['', 'Untrained references: ' + (', '.join(report['untrained_references']) or 'none available'),
        'Full JSON includes idle outcomes, end-position RMS, critic explained variance, LR/KL/clipping, rejected steps, final wall time, and missing-data flags.',
        'Higher tracking cost / lower end tick are screening flags, not proof of regression; inspect paired failure uncertainty and independent training seeds.'])
    if report.get('pending_comparisons'):
        lines.append(f"{len(report['pending_comparisons'])} pending, missing or unplanned comparisons omitted; details retained in JSON.")
    return '\n'.join(lines) + '\n'


def analyze(directory, baseline_name='baseline', updates=(128, 256), repetitions=2000, bootstrap_seed=94721):
    directory = Path(directory)
    results, parse_errors = {}, {}
    for path in sorted(directory.glob('result_*.json')):
        try:
            data = json.loads(path.read_text())
            name = data.get('variant', path.stem[len('result_'):])
            if name in results:
                raise ValueError('Duplicate variant name')
            results[name] = data
        except (ValueError, OSError) as error:
            parse_errors[path.name] = str(error)
    if baseline_name not in results:
        raise ValueError(f'Baseline {baseline_name!r} not found in {directory}')
    baseline = results[baseline_name]
    report = dict(schema_version=1, baseline=baseline_name,
        bootstrap=dict(method='resample evaluation seeds, then paired rows within each selected seed',
            repetitions=repetitions, seed=bootstrap_seed, confidence=.95,
            scope='evaluation sampling only; excludes training-seed variability; exploratory, no multiple-comparison correction'),
        failure_flag=1, parse_errors=parse_errors, variants={}, comparisons=[], pending_comparisons=[], untrained_references={})
    for name, result in results.items():
        report['variants'][name] = dict(complete=result.get('complete'), failed=result.get('failed'),
            error=result.get('error'), training_seed=result.get('training_seed'), settings=result.get('settings'),
            training_worlds=world_counts(result)[0], evaluation_worlds=world_counts(result)[1],
            final_wall_seconds=result.get('elapsed_seconds'), training_wall_seconds=result.get('training_wall_seconds'),
            initialization_seconds=result.get('initialization_seconds'), evaluation_seconds=result.get('evaluation_seconds'),
            evaluation_updates=sorted({e.get('evaluation_update') for e in result.get('evaluations', [])
                if finite(e.get('evaluation_update'))}),
            checkpoint_sha256=result.get('checkpoint_sha256'))
        report['variants'][name]['snapshots'] = {}
        for update in report['variants'][name]['evaluation_updates']:
            entries = index_evaluations(result, update)
            report['variants'][name]['snapshots'][str(update)] = dict(training=training_summary(result, update),
                groups={g: group_summary({s: e for s, e in entries.items()
                    if g == 'perturbed_loco' or e.get('full_normal_horizon', True)}, codes)
                    for g, codes in GROUPS.items()})
        zero = index_evaluations(result, 0)
        if zero:
            report['untrained_references'][name] = {g: group_summary({s: e for s, e in zero.items()
                if g == 'perturbed_loco' or e.get('full_normal_horizon', True)}, codes) for g, codes in GROUPS.items()}
        if name == baseline_name:
            continue
        for update in updates:
            if index_evaluations(result, update) or (result.get('equivalent_update_budget', 0) >= update):
                readiness = comparison_readiness(result, baseline, update)
                if readiness['ready']:
                    report['comparisons'].append(compare(result, baseline, update, repetitions, bootstrap_seed))
                else:
                    report['pending_comparisons'].append(dict(candidate=name, baseline=baseline_name,
                        equivalent_updates=update, **readiness))
    # A dedicated baseline0 is an untrained reference, never a trained control.
    report['notes'] = ['baseline0 / update0 are untrained checkpoint references, not substitutes for baseline at128/256.',
        'Missing or mismatched initial states invalidate paired comparisons; no values are imputed.',
        'Normal-locomotion and combined-idle comparisons exclude seeds marked full_normal_horizon=false in either run.',
        'Training-start hashes are compared only for matching training worlds and seed; held-out evaluation hashes and row order must always match.',
        'Current position arrays are mean squared per-coordinate body-origin errors; RMS cm is sqrt(mean)×100, not mean Euclidean distance.']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--baseline', default='baseline')
    parser.add_argument('--updates', type=int, nargs='+', default=[128, 256])
    parser.add_argument('--bootstrap-repetitions', type=int, default=2000)
    parser.add_argument('--bootstrap-seed', type=int, default=94721)
    parser.add_argument('--output-prefix', default='sweep_comparison')
    args = parser.parse_args()
    if Path(args.output_prefix).name != args.output_prefix:
        parser.error('--output-prefix must be a file stem')
    report = analyze(args.directory, args.baseline, args.updates, args.bootstrap_repetitions, args.bootstrap_seed)
    report['analysis_script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    table = render_table(report)
    (args.directory / (args.output_prefix + '.json')).write_text(json.dumps(report, indent=2, allow_nan=False))
    (args.directory / (args.output_prefix + '.md')).write_text(table, encoding='utf-8')
    print(table)


if __name__ == '__main__':
    main()
