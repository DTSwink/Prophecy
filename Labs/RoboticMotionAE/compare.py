"""Compare two completed architecture trials on identical prepared windows."""
import argparse
import json
from pathlib import Path


def compare(root):
    runs = {name: root / directory for name, directory in
            [('3x1024', 'run'), ('2x512', 'run_2x512')]}
    configs = {name: json.loads((p / 'config.json').read_text()) for name, p in runs.items()}
    shared = ('features_sha256', 'schema', 'latent_dim', 'input_dim', 'batch_size',
              'steps', 'optimizer', 'lr', 'weight_decay', 'seed', 'noise_std',
              'clip_count', 'windows', 'sampling', 'split', 'checkpoint_selection')
    for field in shared:
        assert configs['3x1024'][field] == configs['2x512'][field], field
    rows = {}
    for name, path in runs.items():
        result = json.loads((path / 'completed.json').read_text())
        assert result['state'] == 'complete'
        rows[name] = {key: result[key] for key in (
            'best_step', 'best_validation', 'test_mse', 'train_mse_at_best',
            'parameters', 'elapsed_seconds', 'validation_summary')}
        rows[name]['validation_train_ratio'] = result['best_validation'] / result['train_mse_at_best']
        rows[name]['validation_train_difference'] = result['best_validation'] - result['train_mse_at_best']
    large, small = rows['3x1024'], rows['2x512']
    report = dict(shared_protocol_verified=True, features_sha256=configs['3x1024']['features_sha256'],
                  models=rows, winner_by_validation=min(rows, key=lambda n: rows[n]['best_validation']),
                  validation_improvement_percent=100*(1-small['best_validation']/large['best_validation']),
                  test_improvement_percent=100*(1-small['test_mse']/large['test_mse']),
                  caveat='Single seed; same within-motion holdouts. Test is now a comparison set, not a new untouched test. Lower reconstruction error alone does not prove a better perturbation regularizer.')
    (root / 'architecture-comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', type=Path, required=True)
    compare(parser.parse_args().data_root)
