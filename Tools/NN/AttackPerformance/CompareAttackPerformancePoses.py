"""Compare complete paired pose/state captures, not just a chosen symptom frame."""
import json,pathlib,sys
p=pathlib.Path('Saved/Diagnostics/AttackPerformance')
a=json.loads((p/(sys.argv[1]+'-poses.json')).read_text())
b=json.loads((p/(sys.argv[2]+'-poses.json')).read_text())
assert not a['error'] and not b['error'],(a['error'],b['error'])
assert a.get('events')==b.get('events'),'Different scripted lifecycle events'
assert len(a['rows'])==len(b['rows']) and a['rows'],'Different capture length'
differences=[(x['frame'],y['frame']) for x,y in zip(a['rows'],b['rows']) if x!=y]
result=dict(reference=sys.argv[1],candidate=sys.argv[2],frames=len(a['rows']),identical=not differences,first_differences=differences[:10])
(p/(sys.argv[2]+'-comparison.json')).write_text(json.dumps(result,indent=2))
print(result)
assert not differences,'Pose, carrier or lifecycle state changed'
