from pathlib import Path
import difflib,json,re
out=Path(__file__).parent
def read(p):
 b=p.read_bytes();return b.decode('utf-16' if b.startswith(b'\xff\xfe') else 'utf-8-sig').replace('\r\n','\n')
def blocks(text):
 result={}
 for chunk in text.strip().split('\n\n'):
  lines=chunk.strip().splitlines()
  if lines and lines[0].startswith('/Game/'):
   assert lines[0] not in result
   result[lines[0]]=[re.sub(r'  self= /Engine/Transient.BPGC_ARCH_FOR_CDO_(FixedFrameRateLibrary|ProphecySkinnedMeshBlueprintLibrary)_[0-9]+ ->',r'  self= /Script/GameAnimationSample3.Default__\1 ->',x) for x in lines[1:]]
 return result
before=blocks(read(out/'graph-updated-before.txt'));reload=blocks(read(out/'graph-reload.txt'));after=blocks(read(out/'graph-wired.txt'))
changes=[]
for k,v in before.items():
 if reload.get(k)!=v:changes.append({'node':k,'before':v,'reload':reload.get(k)})
assert not changes,json.dumps(changes,indent=2)
allowed={('UserConstructionScript','K2Node_FunctionEntry_0'),('begin_f','K2Node_FunctionEntry_0'),('begin_f','K2Node_CallFunction_6'),('tick debugging','K2Node_IfThenElse_5')}
changed=[]
for k,v in before.items():
 assert k in after,('Removed node',k)
 if after[k]!=v:
  p=k.split(' | ');assert (p[1],p[2]) in allowed,('Unexpected change',k,v,after[k])
  delta=list(difflib.ndiff(v,after[k]));changed.append({'node':k,'diff':delta})
  assert all(line[2:].strip().startswith(('then=','execute=')) for line in delta if line.startswith(('- ','+ '))),delta
added=[k for k in after if k not in before]
assert len(added)==4,added
assert sum(k.endswith(' | Draw Sword') for k in added)==1
assert sum(k.endswith(' | Set Sword Holster Profile') for k in added)==1
assert sum(k.endswith(' | Capture Sword Holster Reference') for k in added)==2
(out/'graph-verification.json').write_text(json.dumps({'result':'passed','changed':changed,'added':added},indent=2),encoding='utf-8')
print('Full graph verification passed: four additions, four expected execution-link changes; all other nodes/pins/defaults unchanged.')

