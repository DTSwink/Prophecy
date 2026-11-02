"""Check frozen-policy fidelity before considering cheaper native physics."""
import argparse
import json
from pathlib import Path
from analyze_supermimic_pilots import GROUPS, paired


def analyze(folder):
    folder = Path(folder)
    reports = {name: json.loads((folder/name/'result.json').read_text())
               for name in ['original', 'cap4']}
    assert len({r['checkpoint_sha256'] for r in reports.values()}) == 1
    for name, report in reports.items():
        assert report['complete'] and report['method'] == name
        assert report['actor_updates'] == report['policy_max_abs_delta'] == 0
        options = report['options']['actual']
        assert options['physics_hz'] == 240 and options['policy_hz'] == 30
        assert (options['iterations'], options['ls_iterations']) == ((100, 50) if name == 'original' else (4, 4))
        assert {(e['seed'], e['exploration']) for e in report['evaluations']} == {
            (s, n) for s in [984210, 984211] for n in [False, True]}
    times = {name: sum(e['seconds'] for e in r['evaluations']) for name, r in reports.items()}
    speed = times['original']/times['cap4']
    result = dict(warmed_evaluation_seconds=times, warmed_evaluation_speed_ratio=speed,
                  comparisons={}, followup_training_gate=speed >= 1.5,
                  caveat='Frozen-policy physics diagnostic only; no learning speedup. Evaluation includes resets and inference. Different failure rates alter reset overhead. Two T4 workers; GPU-to-GPU variation is not replicated.',
                  setup_and_warmup={n: {k: r[k] for k in ['setup_seconds', 'warmup_seconds', 'total_worker_seconds']} for n, r in reports.items()})
    for noisy in [False, True]:
        cohorts = {n: {'rows': [row for e in r['evaluations'] if e['exploration'] == noisy for row in e['rows']]} for n, r in reports.items()}
        for a, b in zip(cohorts['original']['rows'], cohorts['cap4']['rows']):
            assert a['seed'] == b['seed'] and a['initial_observation_sha256'] == b['initial_observation_sha256']
        comparisons = {g: paired(cohorts['original'], cohorts['cap4'], g) for g in GROUPS}
        result['comparisons']['noisy' if noisy else 'deterministic'] = comparisons
        for group, item in comparisons.items():
            failure_limit = 1 if group.startswith('perturbed') else 2
            acceptable = (item['failure_change_percentage_points'] <= failure_limit
                          and item['after_return'] >= item['before_return'] - .05*abs(item['before_return']))
            result['followup_training_gate'] &= acceptable
    (folder/'verified-native-fidelity.json').write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('folder')
    print(json.dumps(analyze(parser.parse_args().folder), indent=2))
