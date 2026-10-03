import json,re
from pathlib import Path
root=Path(__file__).resolve().parent
def parse(path):
    data=path.read_bytes().decode('utf-16' if path.read_bytes().startswith(b'\xff\xfe') else 'utf-8-sig')
    result={}; key=None
    for line in data.splitlines():
        if line.startswith('/Game'):
            key=line;result[key]=[]
        elif key:result[key].append(line)
    return result
a=parse(root/'graph-before.txt');b=parse(root/'graph-after.txt')
assert a.keys()==b.keys(),'Unexpected node changes'
added=[]
for key in b:
    for line in list(b[key]):
        if line.startswith('  AlphaHold=') and line not in a[key]:
            assert key.endswith('| Set Attack FK Return')
            assert re.fullmatch(r'  AlphaHold=0(?:\.0+)? None ->',line),line
            added.append(key);b[key].remove(line)
    def normalized(lines):
        return [line.replace('  Key=None None ->','  Key= None ->') if '| K2Node_InputKey_' in key else line for line in lines]
    assert normalized(a[key])==normalized(b[key]),key
assert len(added)==1,added
report={'passed':True,'checked_nodes':len(a),'alpha_hold_nodes':added}
(root/'graph-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
