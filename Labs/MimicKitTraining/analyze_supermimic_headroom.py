"""Summarize frozen-policy evaluation headroom without claiming learning gains."""
import json
from pathlib import Path
import sys


def analyze(folder):
    folder = Path(folder)
    result = dict(arms={}, interpretation='Frozen policies only. Differences are not learning or speed gains.')
    for arm in ['current', 'early']:
        report = json.loads((folder/arm/'result.json').read_text())
        assert report['complete'] and report['model_max_abs_delta'] == 0
        assert report['accepted_actor_updates'] == 0
        summary = dict(restored=report['restored'], gpu=report['gpu'],
            checkpoint_sha256=report['checkpoint_sha256'], seconds=report['total_seconds'], modes={})
        for mode, evaluations in report['first_episodes'].items():
            stream = report['continuous'][mode]
            assert stream['initial_perturbed_yaw_min'] < -170 and stream['initial_perturbed_yaw_max'] > 170
            groups = {}
            for group in ['normal_loco', 'perturbed_loco']:
                count = sum(r['groups'][group]['rows'] for r in evaluations)
                failed = sum(r['groups'][group]['failures'] for r in evaluations)
                ret = sum(r['groups'][group]['rows']*r['groups'][group]['mean_return'] for r in evaluations)/count
                groups[group] = dict(first120_rows=count, first120_failures=failed,
                    first120_failure_percent=100*failed/count, first120_mean_return=ret,
                    first120_unfinished=sum(r['groups'][group]['unfinished'] for r in evaluations),
                    continuous480=stream['groups']['all_completed'][group],
                    continuous_after120=stream['groups']['completed_after_tick120'][group],
                    first_cohort_through480=stream['first_cohort'][group])
            summary['modes'][mode] = groups
        result['arms'][arm] = summary
    assert result['arms']['early']['restored']['prior_samples'] == 1640431616
    assert result['arms']['current']['restored']['prior_samples'] == 2409365504
    assert result['arms']['early']['gpu'] == result['arms']['current']['gpu']
    (folder/'verified-headroom.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    analyze(sys.argv[1])
