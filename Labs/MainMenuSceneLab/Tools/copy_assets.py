"""Copy a small, hashed read-only source selection; never migrate a whole project."""
import hashlib,json,pathlib,re,shutil
LAB=pathlib.Path(__file__).resolve().parents[1]
ROOT=LAB.parents[1]
seeds=[
 '_mygame/SKM_UEFN_Mannequin', '_mygame/SK_UEFN_Mannequin',
 'Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop',
 'Characters/UEFN_Mannequin/Animations/Avoidance/M_Neutral_avoid_idle_move_1_0m_RR_Rfoot',
 'Characters/UEFN_Mannequin/Animations/Walk/M_Neutral_Walk_Loop_F',
]
queue=list(seeds); found={}; skipped=[]
while queue:
 rel=queue.pop()
 if rel in found:continue
 src=ROOT/'Content'/(rel+'.uasset')
 if not src.is_file():continue
 data=src.read_bytes();found[rel]=data
 for ref in re.findall(rb'/Game/[A-Za-z0-9_/]+',data):
  dep=ref.decode()[6:]
  # PoseSearch database references in animation metadata are soft editor links.
  if '/PSD_' in dep or '/MotionMatchingData/' in dep:
   skipped.append(dep);continue
  if dep not in found:queue.append(dep)
size=sum(map(len,found.values()))
assert size<150_000_000,(len(found),size)
records=[]
for rel,data in sorted(found.items()):
 dst=LAB/'Content'/(rel+'.uasset');dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists():dst.write_bytes(data)
 records.append({'path':rel+'.uasset','bytes':len(data),'source_sha256':hashlib.sha256(data).hexdigest(),'copied_sha256':hashlib.sha256(dst.read_bytes()).hexdigest()})
out=LAB/'Resources';out.mkdir(exist_ok=True)
ref=pathlib.Path('C:/Users/singerie/AppData/Local/Temp/codex-clipboard-2b655c08-1b69-43d0-9c92-2f686e3b9bab.png')
shutil.copy2(ref,out/'reference.png')
(out/'asset-provenance.json').write_text(json.dumps({'files':records,'total_bytes':size,'skipped_soft_editor_databases':sorted(set(skipped)),'reference_sha256':hashlib.sha256(ref.read_bytes()).hexdigest()},indent=2),encoding='utf-8')
print(json.dumps({'files':len(found),'bytes':size,'all_copies_match':all(x['source_sha256']==x['copied_sha256'] for x in records)}))
