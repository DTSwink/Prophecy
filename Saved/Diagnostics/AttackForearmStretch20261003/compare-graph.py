from pathlib import Path
import re,json
p=Path('Saved/Diagnostics/AttackForearmStretch20261003')
def read(f):
 b=f.read_bytes();s=b.decode('utf-16') if b[:2] in (b'\xff\xfe',b'\xfe\xff') else b.decode('utf-8-sig')
 return {x.splitlines()[0]:x for x in s.replace('\r','').strip().split('\n\n') if x.startswith('/Game/')}
a=read(p/'Before/BlueprintGraph.txt');b=read(p/'after-graph.txt')
changed=[k for k in a.keys()&b.keys() if a[k]!=b[k]]
report={'added':sorted(b.keys()-a.keys()),'removed':sorted(a.keys()-b.keys()),'changed':sorted(changed)}
(p/'graph-diff.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
