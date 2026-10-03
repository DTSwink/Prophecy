"""Independent whole-graph comparison, allowing only removed nodes and their bypasses."""
import json
import re
from pathlib import Path
root=Path(__file__).resolve().parent
def parse(path):
    result={}
    key=None
    data=path.read_bytes()
    for line in data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig').splitlines():
        if line.startswith('/Game'):
            asset,graph,node,title=line.split(' | ',3)
            key=(asset,graph,node)
            result[key]={'title':title,'pins':{}}
        elif key and line.startswith('  '):
            pin,sep,rest=line[2:].partition('=')
            if not sep:continue
            value,sep,links=rest.rpartition(' ->')
            assert sep,line
            result[key]['pins'][pin]={'value':value,'links':list(filter(None,re.split(r' (?=\w+\.)',links.strip())))}
    return result
before=parse(root/'graph-before.txt')
after=parse(root/'graph-after.txt')
removed=set(); pruned=set()
asset='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent'
for line in (root/'cleanup-result.txt').read_text(encoding='utf-8-sig').splitlines():
    if line.startswith(('removed | ','pruned | ')):
        kind,graph,node,_=line.split(' | ',3)
        (removed if kind=='removed' else pruned).add((asset,graph,node))
errors=[]
if set(after)!=set(before)-removed-pruned:errors.append('Unexpected added/removed node set')
def surviving_links(key,links,seen=()):
    result=[]
    for link in links:
        node,pin=link.rsplit('.',1)
        target=(*key[:2],node)
        if target in pruned:continue
        if target in removed:
            if pin not in ('execute','then'):continue
            assert (target,pin) not in seen,'Cycle in removed execution chain'
            other='then' if pin=='execute' else 'execute'
            result+=surviving_links(target,before[target]['pins'].get(other,{}).get('links',[]),seen+((target,pin),))
        else:result.append(link)
    return sorted(result)
for key,node in after.items():
    if key not in before:continue
    old=before[key]
    if node['title']!=old['title'] or set(node['pins'])!=set(old['pins']):
        errors.append([key,'title/pin set changed']);continue
    for pin,current in node['pins'].items():
        previous=old['pins'][pin]
        expected=surviving_links(key,previous['links'])
        if current['value']!=previous['value'] or sorted(current['links'])!=expected:
            errors.append([key,pin,previous,current,expected])
report={'passed':not errors,'removed_controls':len(removed),'pruned_exclusive_inputs':len(pruned),
        'surviving_nodes_checked':len(after),'errors':errors}
(root/'graph-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
assert not errors
