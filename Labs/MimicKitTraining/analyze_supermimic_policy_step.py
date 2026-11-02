"""Paired real outcomes for signed whole-policy steps; no speed claims."""
import json
from pathlib import Path
import sys
from analyze_supermimic_pilots import paired


def analyze(folder):
    folder = Path(folder)
    reports = {n:json.loads((folder/n/'result.json').read_text()) for n in ['ppo','model']}
    assert len({r['checkpoint_sha256'] for r in reports.values()}) == 1
    assert len({r['gpu'] for r in reports.values()}) == 1
    summary = dict(arms={}, limitation='One proposed direction per method. This diagnoses local update geometry; it does not establish learning speed or seed robustness.')
    for name, r in reports.items():
        assert r['complete'] and r['final_model_max_abs_delta'] == 0 and r['original_proposal_l2'] > 0
        assert max(v['kl'] for v in r['calibration'].values()) <= .050001
        item = {k:r[k] for k in ['original_proposal_l2','original_step','scale','calibration','preparation_seconds','audit_seconds']}
        probes = {p['label']:p for p in r['probes']}
        assert set(probes) == {'baseline','raw_positive','raw_negative','scaled_positive','scaled_negative'}
        item['modes'] = {}
        for mode in ['deterministic','noisy']:
            errors = [row['initial_max_abs_error'] for p in probes.values() for row in p['evaluations'][mode]['rows']]
            assert max(errors) <= 2e-4
            first = probes['baseline']['evaluations'][mode]
            item['modes'][mode] = dict(
                versus_baseline={p:{g:paired(first, row['evaluations'][mode],g) for g in ['normal_loco','perturbed_loco']}
                    for p,row in probes.items() if p != 'baseline'},
                positive_vs_negative={size:{g:paired(probes[size+'_negative']['evaluations'][mode],
                    probes[size+'_positive']['evaluations'][mode],g) for g in ['normal_loco','perturbed_loco']}
                    for size in ['raw','scaled']})
        summary['arms'][name] = item
    (folder/'verified-policy-step.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':analyze(sys.argv[1])
