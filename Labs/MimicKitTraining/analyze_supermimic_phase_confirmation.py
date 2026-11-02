"""Keep the two training-seed comparisons separate; do not pool away variation."""
import contextlib
import io
import json
from pathlib import Path

from analyze_supermimic_pilots import analyze


def main(folder):
    folder=Path(folder);summary={'seeds':{},'production_changed':False,
        'limitation':'Two independent training seeds. Motion-cluster intervals describe evaluation variation, not training-seed confidence. Normal episodes evaluated for 120 of 300 ticks; perturbed episodes cover all 120 ticks.'}
    for seed in (92719,38147):
        names=[f'ppo_seed{seed}',f'frozen_seed{seed}']
        with contextlib.redirect_stdout(io.StringIO()):result=analyze(folder,names)
        for name in names:assert result['arms'][name]['training_seed']==seed
        assert not result['arms'][names[0]]['phase_stability']['freeze_perturbed']
        assert result['arms'][names[1]]['phase_stability']['freeze_perturbed']
        target=folder/f'verified-comparison-seed{seed}.json'
        target.write_text(json.dumps(result,indent=2))
        summary['seeds'][str(seed)]={
            'timing':{name:{key:result['arms'][name][key] for key in (
                'accepted_actor_updates','actor_parameter_delta_l2','training_seconds',
                'learning_seconds_excluding_checks','setup_and_baseline_seconds','total_worker_seconds','stop_reason')}
                for name in names},
            'comparison_labels':{'before':'unchanged PPO final evaluation',
                                 'after':'fixed phase predictor final evaluation'},
            'outcomes':{mode:result['comparisons'][mode]['groups'] for mode in ('deterministic','noisy')},
            'within_arm_changes':{name:{mode:result['arms'][name][mode]['groups']
                for mode in ('deterministic','noisy')} for name in names},
            'report':target.name}
    # Replace the generic last-pair output with the explicit multi-seed summary.
    (folder/'verified-confirmation.json').write_text(json.dumps(summary,indent=2))
    (folder/'verified-comparison.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('folder')
    main(parser.parse_args().folder)
