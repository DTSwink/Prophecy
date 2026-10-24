"""Small stdlib-only cache fidelity, coverage and latency check."""
import json, math, time
from pathlib import Path
from run_bank import read_run, metadata

ROOT = Path(__file__).resolve().parent
checks, timings = [], []
for gait in ('run', 'walk'):
    for drawn in (False, True):
        stem, meta = metadata(gait, drawn)
        default = json.loads((ROOT/'data'/(gait+'-default'+('-drawn' if drawn else '')+'.json')).read_text())
        cached = read_run(gait, 1, 0, drawn)
        assert json.loads(json.dumps(cached['poses'])) == default['poses']
        assert json.loads(json.dumps(cached['roots'])) == default['roots']
        checks.append(stem+' exact default output')
        assert read_run(gait, 1, 1, drawn)['poses'] == cached['poses']
        checks.append(stem+' 100 percent wraps to zero')
        for slot in range(meta['stride']+1):
            phase = min(slot/meta['stride'], .999999)
            start = time.perf_counter()
            data = read_run(gait, 5, phase, drawn)
            timings.append((time.perf_counter()-start)*1000)
            assert len(data['poses']) == 152
            assert all(math.isfinite(v) for p in data['poses'] for xyz in p['points'] for v in xyz)
            assert abs((data['roots'][-1][2]-data['roots'][0][2])/(151/30)-(5 if gait=='run' else 2)) < .001
        checks.append(stem+' every phase covers five seconds at correct speed')
        assert len(read_run(gait, .1, .44, drawn)['poses']) == 5
        checks.append(stem+' short duration slices without inference')
for file,phase in [('phase-check-0.44.json',.44),('contact-check.json',.67)]:
    expected=json.loads((ROOT/'data'/file).read_text())
    actual=read_run('run',1,phase,True)
    assert json.loads(json.dumps(actual['poses']))==expected['poses']
    checks.append('Exact recorded Run phase '+str(phase))
receipt=dict(passed=True,checks=checks,maxReadMs=max(timings),meanReadMs=sum(timings)/len(timings),rollouts=len(timings))
(ROOT/'phase-bank-verification.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
