"""Summarize paired native optimization benchmarks; never modifies Unreal."""
import argparse
import csv
import json
from pathlib import Path
from statistics import median

parser=argparse.ArgumentParser()
parser.add_argument('--directory',type=Path,default=Path('Saved/Diagnostics/SwordOptimization20261010'))
args=parser.parse_args()
with (args.directory/'benchmark.csv').open(encoding='utf-8-sig',newline='') as f:
    rows=list(csv.DictReader(f))
results=[]
for motion,sheathe in sorted({(r['motion'],r['sheathe']) for r in rows}):
    for stage in sorted({r['stage'] for r in rows}):
        selected=[r for r in rows if (r['motion'],r['sheathe'],r['stage'])==(motion,sheathe,stage)]
        old=[r for r in selected if r['old']=='1'];new=[r for r in selected if r['old']=='0']
        before=median(float(r['total_ms'])/int(r['frames']) for r in old)
        after=median(float(r['total_ms'])/int(r['frames']) for r in new)
        result={'motion':motion,'sheathe':sheathe=='1','stage':stage,'before_ms':before,'after_ms':after,'speedup':before/after,
                'before_peak_ms':median(float(r['peak_ms']) for r in old),'after_peak_ms':median(float(r['peak_ms']) for r in new),
                'frames_before':sorted({int(r['frames']) for r in old}),'frames_after':sorted({int(r['frames']) for r in new})}
        results.append(result)
        print(f"{motion:4} {'S' if sheathe=='1' else 'D'} {stage:12} {before:9.6f} -> {after:9.6f} ms {before/after:5.2f}x peak {result['before_peak_ms']:.4f}->{result['after_peak_ms']:.4f}")
summary={'method':'Seven alternating-order paired trials after warmup; same process, same inputs, 100 synchronized agents. Medians. No staggering, reduced update rate or shared cross-agent results. Cycle is procedural-only; planning excludes skeleton discovery/NN reads/runtime admission.',
         'parity':(args.directory/'parity.txt').read_text(encoding='utf-16' if (args.directory/'parity.txt').read_bytes().startswith(b'\xff\xfe') else 'utf-8-sig').strip(),
         'results':results}
(args.directory/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
