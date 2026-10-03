import json,pathlib
p=pathlib.Path('Saved/Diagnostics/Pelvis360-baseline-nn.jsonl')
r=[json.loads(l) for l in p.read_text().splitlines()]
print(r[0].keys());print([(x['actor'],x['time'],x['attack']) for x in r[:5]])
