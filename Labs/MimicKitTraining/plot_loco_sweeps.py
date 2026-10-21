"""Stratified paired locomotion comparisons and a standalone learning-speed plot.

CPU/local files only. Uses analyze_loco_sweeps without altering its statistics.
Example: python plot_loco_sweeps.py LOCAL_DIRECTORY --baseline baseline
"""
import argparse
import json
from pathlib import Path

import numpy as np

import analyze_loco_sweeps as analysis


STRATA = (
    ('yaw', '0–45°', lambda e, i: 0 <= abs(e['initial_yaw_degrees'][i]) < 45),
    ('yaw', '45–90°', lambda e, i: 45 <= abs(e['initial_yaw_degrees'][i]) < 90),
    ('yaw', '90–135°', lambda e, i: 90 <= abs(e['initial_yaw_degrees'][i]) < 135),
    ('yaw', '135–180°', lambda e, i: 135 <= abs(e['initial_yaw_degrees'][i]) <= 180),
    ('gait', 'walk', lambda e, i: e['gait'][i] == 0),
    ('gait', 'run', lambda e, i: e['gait'][i] == 1),
)


def load_results(directory):
    results = {}
    for path in sorted(Path(directory).glob('result_*.json')):
        try:
            data = json.loads(path.read_text())
            results[data.get('variant', path.stem[7:])] = data
        except (OSError, ValueError):
            continue  # The primary analyzer reports unreadable files.
    return results


def stratified_comparison(candidate, baseline, comparison, repetitions, bootstrap_seed):
    output = dict(candidate=comparison['candidate'], baseline=comparison['baseline'],
                  equivalent_updates=comparison['equivalent_updates'],
                  paired_valid=comparison['paired_valid'], errors=comparison['errors'], strata=[])
    if not comparison['paired_valid']:
        return output
    update = comparison['equivalent_updates']
    c = analysis.index_evaluations(candidate, update)
    b = analysis.index_evaluations(baseline, update)
    for category, label, selector in STRATA:
        deltas = []
        count = cfail = bfail = improved = worsened = cunfinished = bunfinished = 0
        contributing_seeds = []
        for seed in comparison['matching_seeds']:
            ids = [i for i, group in enumerate(c[seed]['group']) if group == 1 and selector(c[seed], i)]
            if not ids:
                continue
            contributing_seeds.append(seed)
            cf = np.array([c[seed]['final_done'][i] == 1 for i in ids], dtype=np.int8)
            bf = np.array([b[seed]['final_done'][i] == 1 for i in ids], dtype=np.int8)
            count += len(ids)
            cfail += int(cf.sum())
            bfail += int(bf.sum())
            improved += int(((cf == 0) & (bf == 1)).sum())
            worsened += int(((cf == 1) & (bf == 0)).sum())
            cunfinished += sum(c[seed]['final_done'][i] == 0 for i in ids)
            bunfinished += sum(b[seed]['final_done'][i] == 0 for i in ids)
            deltas.append(cf - bf)
        output['strata'].append(dict(category=category, stratum=label, rows=count,
            matching_seeds=contributing_seeds, candidate_failures=cfail, baseline_failures=bfail,
            candidate_unfinished=cunfinished, baseline_unfinished=bunfinished,
            candidate_failure_percent=100 * cfail / count if count else None,
            baseline_failure_percent=100 * bfail / count if count else None,
            failure_difference_pp=100 * (cfail - bfail) / count if count else None,
            paired_bootstrap_95ci_pp=analysis.paired_interval(deltas, repetitions, bootstrap_seed)
                if deltas else None,
            improved_rows=improved, worsened_rows=worsened))
    return output


def stratified_table(rows):
    lines = ['Perturbed locomotion only. Negative differences favor the candidate.',
        'Absolute initial yaw; bins are left-inclusive/right-exclusive, except180° is included in the last bin.',
        'Paired95% intervals cover evaluation uncertainty only; exploratory subgroups, no multiple-comparison adjustment.', '',
        '| Variant | Eq.updates | Subgroup | Rows | Baseline fail % | Candidate fail % | Difference pp [95% CI] |',
        '|---|---:|---|---:|---:|---:|---|']
    for row in rows:
        if not row['paired_valid']:
            continue
        for s in row['strata']:
            ci = s['paired_bootstrap_95ci_pp']
            interval = f'[{ci[0]:+.2f}, {ci[1]:+.2f}]' if ci else '[missing]'
            lines.append(f"| {row['candidate']} | {row['equivalent_updates']} | {s['stratum']} | {s['rows']} | "
                f"{analysis.format_number(s['baseline_failure_percent'])} | {analysis.format_number(s['candidate_failure_percent'])} | "
                f"{analysis.format_number(s['failure_difference_pp'])} {interval} |")
    if not any(r['paired_valid'] for r in rows):
        lines.append('\nNo valid paired candidate evaluations available yet.')
    return '\n'.join(lines) + '\n'


def complete_points(result):
    """Only show a snapshot once every planned evaluation seed is present."""
    expected = result.get('evaluation_seeds')
    if not isinstance(expected, list) or not expected:
        return [], ['Missing planned evaluation_seeds; plot omitted']
    points, omitted = [], []
    updates = sorted({e.get('evaluation_update') for e in result.get('evaluations', [])
                      if analysis.finite(e.get('evaluation_update'))})
    for update in updates:
        entries = analysis.index_evaluations(result, update)
        if set(entries) != set(expected):
            omitted.append(f'Update{update}: {len(entries)}/{len(expected)} planned seeds; not plotted')
            continue
        if any(analysis.check_entry(e) for e in entries.values()):
            omitted.append(f'Update{update}: invalid evaluation entry; not plotted')
            continue
        summary = analysis.group_summary(entries, (1,))
        timing = analysis.training_summary(result, update)
        seconds = timing['cumulative_update_seconds']
        if not analysis.finite(seconds) or not analysis.finite(summary['failure_percent']):
            omitted.append(f'Update{update}: missing timing/failure rate; not plotted')
            continue
        points.append(dict(update=update, training_minutes=seconds / 60,
                           failure_percent=summary['failure_percent'], rows=summary['rows'],
                           seeds=len(entries)))
    return points, omitted


def plot(report, results, directory, prefix, variants=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, (ax, delta_ax) = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={'width_ratios': [1.1, 1]})
    plt.rcParams.update({'font.family': 'DejaVu Sans'})
    selected = set(variants) | {report['baseline']} if variants else set(results)
    metadata = dict(points={}, omitted={}, selected_variants=sorted(selected),
                    figure_scope='completed variants and completed planned evaluation sets only')
    plotted = set()
    for name, result in results.items():
        if name not in selected:
            continue
        if not result.get('complete'):
            metadata['omitted'][name] = ['Variant is incomplete; not plotted']
            continue
        points, omitted = complete_points(result)
        metadata['points'][name], metadata['omitted'][name] = points, omitted
        if not points:
            continue
        plotted.add(name)
        points.sort(key=lambda p: p['training_minutes'])
        ax.plot([p['training_minutes'] for p in points], [p['failure_percent'] for p in points],
                marker='o', linewidth=2.4 if name == report['baseline'] else 1.7,
                linestyle='-' if len(points) > 1 else 'None', label=name)
    ax.set(xlabel='Measured training time (minutes)', ylabel='Perturbed locomotion failures (%)',
           title='Learning speed • lower is better', xlim=(0, None))
    ax.grid(alpha=.2)
    if plotted:
        ax.legend(fontsize=8, loc='best')
    else:
        ax.text(.5, .5, 'No complete evaluation sets yet', transform=ax.transAxes, ha='center')
    # Latest available common update per variant. Never plot an incomplete set
    # merely because it has some matching seeds and therefore a numerical CI.
    latest = {}
    for comparison in report['comparisons']:
        name = comparison['candidate']
        update = comparison['equivalent_updates']
        candidate_points = metadata['points'].get(name, [])
        baseline_points = metadata['points'].get(report['baseline'], [])
        if comparison['paired_valid'] and any(p['update'] == update for p in candidate_points) and any(p['update'] == update for p in baseline_points):
            if name not in latest or update > latest[name]['equivalent_updates']:
                latest[name] = comparison
    comparisons = sorted(latest.values(), key=lambda r: r['groups']['perturbed_loco']['failure_difference_pp'])
    for index, row in enumerate(comparisons):
        group = row['groups']['perturbed_loco']
        diff, ci = group['failure_difference_pp'], group['paired_bootstrap_95ci_pp']
        if ci:
            delta_ax.plot(ci, [index, index], color='#34495e', linewidth=2)
        delta_ax.scatter([diff], [index], color='#087f5b' if diff < 0 else '#c44536', s=45, zorder=3)
    if comparisons:
        delta_ax.set_yticks(range(len(comparisons)), [f"{r['candidate']} @ {r['equivalent_updates']}" for r in comparisons], fontsize=8)
        delta_ax.invert_yaxis()
    else:
        delta_ax.set_yticks([])
        delta_ax.text(.5, .5, 'Paired candidate comparisons pending', transform=delta_ax.transAxes, ha='center')
    delta_ax.axvline(0, color='#888888', linestyle='--', linewidth=1)
    delta_ax.grid(axis='x', alpha=.2)
    delta_ax.set(xlabel='Failure difference versus baseline (percentage points)',
                 title='Matched sample budget • left favors candidate')
    fig.suptitle('Locomotion sweep — held-out starts', fontsize=15)
    fig.text(.5, .035, 'Evaluation/init time excluded from training axis. Lines only connect measured snapshots; single points do not establish a slope.\n'
             'Intervals: paired evaluation sampling uncertainty only; independent training-seed confirmation is still required.',
             ha='center', fontsize=8, color='#555555')
    fig.tight_layout(rect=(0, .11, 1, .94), w_pad=2.5)
    files = []
    for suffix in ('png', 'svg'):
        path = directory / (prefix + '.' + suffix)
        fig.savefig(path, dpi=160, facecolor='white')
        files.append(str(path))
    plt.close(fig)
    metadata['files'] = files
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--baseline', default='baseline')
    parser.add_argument('--updates', type=int, nargs='+', default=[128, 256])
    parser.add_argument('--bootstrap-repetitions', type=int, default=2000)
    parser.add_argument('--bootstrap-seed', type=int, default=94721)
    parser.add_argument('--output-prefix', default='sweep_learning_speed')
    parser.add_argument('--variants', nargs='+', help='Plot only these variants; baseline is always included')
    args = parser.parse_args()
    if Path(args.output_prefix).name != args.output_prefix:
        parser.error('--output-prefix must be a file stem')
    results = load_results(args.directory)
    if args.variants and any(name not in results for name in args.variants):
        parser.error('Unknown --variants: ' + ', '.join(name for name in args.variants if name not in results))
    report = analysis.analyze(args.directory, args.baseline, args.updates, args.bootstrap_repetitions, args.bootstrap_seed)
    strata = [stratified_comparison(results[r['candidate']], results[r['baseline']], r,
        args.bootstrap_repetitions, args.bootstrap_seed) for r in report['comparisons']]
    table = stratified_table(strata)
    metadata = plot(report, results, args.directory, args.output_prefix, args.variants)
    output = dict(stratified_comparisons=strata, plot=metadata, bootstrap=report['bootstrap'],
                  pending_comparisons=report['pending_comparisons'],
                  notes=['Perturbed locomotion only; all completed120-tick seed sets retained.',
                         'No censored normal-row failure rates enter these subgroup comparisons.',
                         'Primary analysis statistical calculations are unchanged.'])
    (args.directory / (args.output_prefix + '.json')).write_text(json.dumps(output, indent=2, allow_nan=False))
    (args.directory / (args.output_prefix + '.md')).write_text(table, encoding='utf-8')
    print(table)
    print('Figure:', ', '.join(metadata['files']))


if __name__ == '__main__':
    main()
