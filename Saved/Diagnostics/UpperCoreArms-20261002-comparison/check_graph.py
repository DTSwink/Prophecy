from pathlib import Path
import re, json
folder=Path(__file__).resolve().parent
root=folder.parents[2]
def read(path):
    b=path.read_bytes()
    return b.decode('utf-16' if b.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
def rows(text):
    result={}
    node=''
    for line in text.splitlines():
        if line.startswith('/Game/'):
            node=line
        elif line.startswith('  '):
            key=line.split('=',1)[0].strip()
            if key in ('ArmsResponseTimeSeconds','ArmsBlendToNormalDurationSeconds'):continue
            if key=='self':
                line=re.sub(r'= .*? ->','= LIBRARY ->',line)
            result[(node,key)]=line
    return result
before=rows(read(folder/'graph-before-rollback-refresh.txt'))
after=rows(read(root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt'))
changes=[{'node':k[0],'pin':k[1],'before':before.get(k),'after':after.get(k)} for k in before.keys()|after.keys() if before.get(k)!=after.get(k)]
(folder/'graph-check.json').write_text(json.dumps(changes,indent=2))
print('Existing graph pin/value/link differences:',len(changes))
assert not changes, changes[:8]
text=read(root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt')
assert 'ArmsResponseTimeSeconds=' not in text and 'ArmsBlendToNormalDurationSeconds=' not in text
print('Original pins restored; all other graph values and links preserved.')
