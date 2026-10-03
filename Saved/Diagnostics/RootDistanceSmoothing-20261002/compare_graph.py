from pathlib import Path
import json,re
p=Path(__file__).resolve().parent
def normalize(line):
 # Live Coding swaps unlinked static-library default-object identities.
 if line.startswith('  self= '):
  line=re.sub(r'/Engine/Transient\.BPGC_ARCH_FOR_CDO_(\w+)_\d+(?= ->$)',r'/Script/GameAnimationSample3.Default__\1',line)
 return re.sub(r'Default__REINST_(\w+?)_\d+',r'Default__\1',line)
def read(name):
 result={}
 data=(p/name).read_bytes()
 text=data.decode('utf16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig').replace('\r\n','\n')
 for block in text.strip().split('\n\n'):
  lines=block.splitlines()
  if lines and lines[0].startswith('/Game/'):
   result[lines[0]]=sorted(normalize(line) for line in lines[1:])
 return result
a,b=read('graph-before.txt'),read('graph-after.txt')
assert a.keys()==b.keys(),(a.keys()-b.keys(),b.keys()-a.keys())
changes=[];nodes=0
for key in a:
 old,new=a[key],b[key]
 if key.endswith(' | SetLocomotionRootWindowSmoothing') or key.endswith(' | GetLocomotionRootWindowSmoothing'):
  added=[v for v in new if v.strip().startswith('DistanceDeceleration=')]
  assert len(added)==1,(key,added)
  if key.endswith(' | SetLocomotionRootWindowSmoothing'):assert float(added[0].split('=',1)[1].split()[0])==-1
  new=[v for v in new if v not in added];nodes+=1
 if old!=new:changes.append(dict(node=key,before=old,after=new))
r=dict(nodes_checked=len(a),root_smoothing_nodes=nodes,unexpected_changes=changes)
(p/'graph-comparison.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps(dict(nodes_checked=len(a),root_smoothing_nodes=nodes,unexpected_change_count=len(changes)),indent=2))
assert not changes
