"""Summarize frozen-policy objective probes, never claim a learning speedup."""
import json
import sys
from pathlib import Path

import numpy as np


def analyze(folder):
    folder = Path(folder)
    summary = dict(policy_learning_test=False, arms={})
    for arm in ('deterministic', 'noisy'):
        result = json.loads((folder / arm / 'result.json').read_text(encoding='utf-8'))
        assert result['complete'] and result['policy_parameter_delta_l2'] == 0
        assert result['exploration'] == (arm == 'noisy')
        grouped = {}
        for row in result['probes']:
            grouped.setdefault((row['seed'], row['prefix_ticks']), {})[row['component']] = row
        assert len(grouped) == 4
        comparisons = []
        for (seed, prefix), rows in grouped.items():
            assert set(rows) == {'dense', 'dense_critic', 'full'}
            reference = rows['dense']
            mask = np.asarray(reference['row_valid'], dtype=bool)
            motions = np.asarray(reference['row_motion'])[mask]
            baseline = np.asarray(reference['row_return_delta'])[mask]
            for name, row in rows.items():
                assert row['row_valid'] == reference['row_valid']
                values = np.asarray(row['row_return_delta'])[mask]
                failures = np.asarray(row['row_failure_delta'])[mask]
                assert np.isfinite(values).all()
                # Paired motion-cluster resampling; not an independent-training-seed CI.
                clusters = [np.flatnonzero(motions == m) for m in np.unique(motions)]
                rng = np.random.default_rng(seed + prefix)
                diffs = []
                for _ in range(1000):
                    ids = np.concatenate([clusters[i] for i in rng.integers(len(clusters), size=len(clusters))])
                    diffs.append(float((values - baseline)[ids].mean()))
                comparisons.append(dict(seed=seed, prefix_ticks=prefix, component=name, rows=int(mask.sum()),
                    positive_fraction=float((values > 0).mean()),
                    mean_discounted_return_difference=float(values.mean()),
                    median_discounted_return_difference=float(np.median(values)),
                    failure_count_difference=int(failures.sum()),
                    mean_difference_versus_dense=float((values-baseline).mean()),
                    versus_dense_motion_cluster_interval_95=np.quantile(diffs, [.025, .975]).tolist()))
        summary['arms'][arm] = dict(seconds=result['seconds'], checks=result['checks'], comparisons=comparisons)
    summary['limits'] = ('One action changed, followed by the unchanged policy to tick120. '
                         'Local gradient advice only; no actor updates or learning-speed claim. '
                         'Confidence intervals resample motions, not independent training runs.')
    (folder / 'verified-objective-comparison.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    for arm, result in summary['arms'].items():
        for r in result['comparisons']:
            print(arm, r['seed'], r['prefix_ticks'], r['component'], 'rows', r['rows'],
                  'positive%', round(r['positive_fraction']*100, 2),
                  'return +/-', round(r['mean_discounted_return_difference'], 5),
                  'failures +/-', r['failure_count_difference'],
                  'versus dense CI', [round(x, 4) for x in r['versus_dense_motion_cluster_interval_95']])
    return summary


if __name__ == '__main__':
    analyze(sys.argv[1])
