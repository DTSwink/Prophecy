"""Collect every numerical lab regression result, without touching the desktop."""
import subprocess, pathlib, json, time, sys
root = pathlib.Path(__file__).resolve().parents[2]
out = root / (sys.argv[1] if len(sys.argv) > 1 else 'Saved/Diagnostics/SwordOvernight20261011/lab')
out.mkdir(parents=True, exist_ok=True)
excluded = {'test_bodyreach_ui.cjs', 'test_capture.cjs', 'test_keyboard.cjs', 'test_retime_ui.cjs', 'test_duration.cjs'}
results = []
for test in sorted((root / 'Labs/SwordHolsterLab').glob('test*.cjs')):
    if test.name in excluded: continue
    start = time.monotonic()
    try:
        run = subprocess.run(['node', str(test)], cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=240)
        code, log = run.returncode, run.stdout + run.stderr
    except subprocess.TimeoutExpired as e:
        code, log = -1, str(e)
    (out / (test.stem + '.log')).write_text(log, encoding='utf-8')
    results.append(dict(test=test.name, exit=code, seconds=time.monotonic()-start))
    (out / 'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(test.name, code, flush=True)
sys.exit(any(r['exit'] != 0 for r in results))
