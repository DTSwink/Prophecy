"""CPU-only recorder coverage contracts, including the ordered 512-world fixture."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
from observe_many import select_replay_worlds

rows=json.loads((ROOT/'Saved/MimicKitEquipment/package/prepared/manifest.json').read_text())['motions']
counts=json.loads((ROOT/'Saved/MimicKitEquipment/run-weight-allocation.json').read_text())['per_clip']
motions=[i for idle in (True,False) for i,r in enumerate(rows) if (r['gait']==-1)==idle for _ in range(counts[r['id']])]
equipment=[r['sword_drawn'] for r in rows];original=motions.copy();covered=set()
for cycle in range(24):
    ids=select_replay_worlds(motions,31,equipment,20,cycle)
    assert len(set(ids))==20
    assert sum(equipment[motions[w]] for w in ids)==10
    assert sum(w<31 for w in ids)==2
    assert len({motions[w] for w in ids})==20
    covered.update(motions[w] for w in ids)
assert len(covered)==50 and motions==original
for count in (1,2,3,19,20,51,512,600):
    ids=select_replay_worlds(motions,31,equipment,count,0)
    assert len(ids)==len(set(ids))==min(count,512)
assert len(select_replay_worlds([0]*5,0,[False],20,0))==5
assert len(select_replay_worlds([0,1,1,1],0,[False,True],4,0))==4
print('PASS: balanced 10/10, two idles, unique clips, full rotating coverage, bounded fallback; no training mutations')
