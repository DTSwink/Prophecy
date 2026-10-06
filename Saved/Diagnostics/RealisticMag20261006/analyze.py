import json,pathlib,re
p=pathlib.Path(__file__).parent
log=(p/'editor.log').read_text(encoding='utf-8',errors='replace')
tests=re.findall(r'Test Completed\. Result=\{(.*?)\} Name=\{.*?\} Path=\{(.*?)\}',log)
assert len(tests)==26 and all(r=='Success' for r,n in tests),tests
d=json.loads((p/'live.json').read_text())
assert d['reason']=='complete',d['reason']
assert any(e.get('threshold_crossings')==4 and e.get('mode_strength_unchanged') for e in d['events'])
probe=json.loads((p/'probe.json').read_text())
assert probe['reason']=='complete',probe['reason']
assert probe['events']==['start','end','start','end']
checks={}
for tick,want in [(30,.7),(45,.35),(60,0.)]:
 r=next(r for r in probe['rows'] if r['tick']==tick)
 got=r['hand_r'];assert abs(got-want)<.002,(tick,got,want)
 checks[tick]=got
for r in d['rows']:
 if r['tick']>=650 and r['actor']=='BP_ProphecyManualPoseAgent':
  assert r['modes']['upperarm_r']==1 and r['modes']['lowerarm_r']==.25 and r['modes']['hand_r']==.25,r
out={'native_tests':tests,'live_rows':len(d['rows']),'actors':sorted({r['actor'] for r in d['rows']}),'max_span_cm':max(r['max_span'] for r in d['rows']),'events':d['events'],'hold_blend_hand_samples':checks,'probe_event_dispatch':probe['events'],'scope':'900 tick scene: mixed modes retained on player; NPC Blueprint overwrites mode to .25. Isolated native probe verifies uncancelled hold/blend and event dispatch.'}
(p/'validation.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
