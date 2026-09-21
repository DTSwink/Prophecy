from pathlib import Path
import json,re
folder=Path('Saved/Diagnostics/RemoveParryBlocker')
d=json.loads((folder/'PIE.json').read_text())
assert not d['error'],d['error']
modes=sorted(set(r['opponent']['activity'] for r in d['rows']))
print('samples',len(d['rows']),'defender modes',modes)
s=(folder/'After.copy').read_text(encoding='utf-8-sig')
nodes=[n for n in re.split(r'(?=\s+Begin Object Class=)',s) if 'MemberName="StartNNParry"' in n]
assert nodes
assert not any('PinName="Blocker"' in n for n in nodes)
print('Parry calls',len(nodes),'no Blocker pins')
episodes=[];previous=None
for r in d['rows']:
    a=r['player']['attack'];v=r['opponent']['defense']
    if not a or not v:continue
    if a[3] and (previous is None or a[4]<previous):
        episodes.append(dict(dodge=r['dodge'],hit=a[4],defender=r['opponent']['activity']))
    previous=a[4] if a[3] else None
print('Hit observations',episodes)
(folder/'summary.json').write_text(json.dumps(dict(samples=len(d['rows']),modes=modes,hit_observations=episodes,blocker_pins=0),indent=2))
p=Path('ProjectJournal.md');journal=p.read_text(encoding='utf-8')
entry='''- Parry Blocker selection REMOVED (2026-09-17): Start NN Parry now takes Agent, Attacker, duration and Out Error only. Removed EProphecyParryBlocker, queued blocker storage, selected-arm masks, blade-only eligibility check, and block-vs-harm ordering/flags throughout native code. Get NN Defense Status retains active/steps/attacker-frame/contact collider/time, without Blocked or HarmfulContact. Kinematic PHAT/sword stopping uses the earliest confirmed contact from any defender body; Sim/HalfSim Hit ownership, Armed activation, Parry Hit finish and Dodge Hit+X deadline unchanged. NN inputs/outputs unchanged. Existing BP call surgically refreshed, compile passed; user's already-dirty BP left unsaved, map untouched. Backup and test evidence: Saved/Diagnostics/RemoveParryBlocker. Live Coding succeeded (402.69s, memory-limited serial compilation), no restart. PhysicalContactShapes, ParryContacts and ParryRecurrence automation passed; short disposable PIE completed without errors (Parry/Dodge results in summary.json). Historical classified contact reports describe the removed behavior and are not current gameplay semantics.\n\n'''
first=journal.find('\n')+1
p.write_text(journal[:first]+'\n'+entry+journal[first:],encoding='utf-8')
