"""Summarize the paired 100-agent native stagger benchmark; no Unreal writes."""
import csv
import json
import pathlib
import statistics
import sys

sys.stdout.reconfigure(encoding='utf-8')

root = pathlib.Path(__file__).resolve().parents[2]
source = root / 'Saved/Diagnostics/SwordStagger20261011'
rows = list(csv.DictReader((source / 'benchmark.csv').open(encoding='utf-8-sig')))
names = ['idle draw', 'idle sheathe', 'walk draw', 'walk sheathe', 'mixed simultaneous', 'mixed arrivals over 19 ticks']
summary = dict(method='Seven alternating paired repeats after warmup, 100 independent agents. Includes initial pose math on admission ticks. Excludes NN reads/inference, skeleton discovery, cache publication, equipment, physics and rendering.', cases=[])
lines = ['# D/S staggering — October 11, 2026', '',
         'Four independent start bookings and four balanced reach-refresh slots. The player starts immediately. Crowd starts wait at most three unpaused world ticks; motion continues every tick after admission.', '',
         'Same-process medians for 100 agents, including initial pose planning in its actual admission tick:', '',
         '| Fixture | Mean ms before → after | Peak ms before → after | Start-tick peak ms before → after |',
         '| --- | ---: | ---: | ---: |']
for scenario, name in enumerate(names):
    case = dict(name=name)
    for stagger in [0, 1]:
        group = [r for r in rows if int(r['scenario']) == scenario and int(r['stagger']) == stagger]
        assert len(group) == 7
        values = {key: statistics.median(float(r[key]) for r in group)
                  for key in ['frames', 'total_ms', 'peak_ms', 'start_peak_ms', 'cycle_peak_ms', 'max_starts', 'max_refits']}
        values['mean_ms'] = statistics.median(float(r['total_ms']) / int(r['frames']) for r in group)
        values['worst_observed_ms'] = max(float(r['peak_ms']) for r in group)
        case['after' if stagger else 'before'] = values
    summary['cases'].append(case)
    a, b = case['before'], case['after']
    lines.append(f"| {name} | {a['mean_ms']:.3f} → {b['mean_ms']:.3f} | {a['peak_ms']:.3f} → {b['peak_ms']:.3f} | {a['start_peak_ms']:.3f} → {b['start_peak_ms']:.3f} |")
lines += ['', 'Peak means the median of the seven per-run maxima; the JSON also retains the largest observed maximum. The four single-action fixtures use recorded idle/walk input. The mixed-arrival fixture combines those actions and accepts requests over 19 ticks.', '',
          summary['method'], '', 'Staggering spreads work across ticks; it is not a reduction in the amount of animation work. Mean includes the slightly longer crowd window caused by delayed starts, so total CPU time is also retained in the JSON.', '',
          'Reproduce with `Tools/SwordHolster/RunParity.ps1 -Tests Prophecy.SwordHolster.Stagger`, then `Tools/SwordHolster/SummarizeStagger.py`.']
receipt = root / 'Tools/SwordHolster/Stagger20261011.json'
if receipt.exists():
    existing = json.loads(receipt.read_text(encoding='utf-8'))
    existing.update(summary)
    summary = existing
receipt.write_text(json.dumps(summary, indent=2), encoding='utf-8')
report = root / 'Tools/SwordHolster/Stagger20261011.md'
validation = ''
if report.exists():
    previous = report.read_text(encoding='utf-8')
    marker = '\n## Implementation and validation\n'
    if marker in previous:
        validation = marker + previous.split(marker, 1)[1]
report.write_text('\n'.join(lines) + '\n' + validation, encoding='utf-8')
print('\n'.join(lines))
