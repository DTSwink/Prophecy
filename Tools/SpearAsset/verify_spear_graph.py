"""Compare every copied Blueprint pin connection against the original snapshot."""
import pathlib,json,re
out=pathlib.Path(__file__).resolve().parents[2]/'Saved/Diagnostics/SpearPike20261030'
log=(out/'editor-final.log').read_text(encoding='utf-8',errors='replace')
commands=json.loads((out/'disabled-test-node-commands.json').read_text())
disabled={}
for name,path in commands['paths'].items():
    states=re.findall(re.escape(path)+r'\.EnabledState = (\w+)',log)
    assert states and states[-1]=='Disabled',(name,states)
    disabled[name]=states[-1].upper()
(out/'disabled-test-nodes.json').write_text(json.dumps({'after':disabled,'evidence':'editor-final.log GETALL exact object paths'},indent=2))
def parse(path,original=False):
    nodes={};pins={};key=None
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if ' | ' in line and not line.startswith(' '):
            fields=line.split(' | ')
            if original:fields=fields[1:]
            key=tuple(fields[:2]);nodes[key]=' | '.join(fields[2:])
        elif key and line.startswith('  ') and ' ->' in line:
            pin,targets=line.strip().split(' ->',1)
            pins[(*key,pin.split('=',1)[0])]=sorted(targets.split())
    return nodes,pins
_,before=parse(out/'A_Sword_graph_before.txt',True);nodes,after=parse(out/'SpearSetup.txt')
assert before.keys()==after.keys(),'Unexpected added/deleted pin'
changed=[(k,before[k],after[k]) for k in before if before[k]!=after[k]]
allowed={
    ('EventGraph','K2Node_IfThenElse_11','then'),('EventGraph','K2Node_VariableSet_1','execute'),
    ('EventGraph','ProphecyOptimisedHitMode','Condition'),('handle cuts f','ProphecyOptimisedSkipTick','Condition'),
    ('Stain Blade','K2Node_CallFunction_9','X'),('Stain Blade','K2Node_CallFunction_9','Y'),('Stain Blade','K2Node_CallFunction_20','A'),
}
# The reciprocal ends of the two former Optimised condition links.
for graph,node,pin in [('EventGraph','ProphecyOptimisedHitMode','Condition'),('handle cuts f','ProphecyOptimisedSkipTick','Condition')]:
    for target in before[(graph,node,pin)]:
        other_node,other_pin=target.split('.',1);allowed.add((graph,other_node,other_pin))
unexpected=[c for c in changed if c[0] not in allowed];assert not unexpected,unexpected
for key in [('EventGraph','K2Node_IfThenElse_11','then')]:
    assert not after[key],key
disabled=json.loads((out/'disabled-test-nodes.json').read_text())['after']
assert len(disabled)==3 and all('DISABLED' in x for x in disabled.values())
assert nodes[('rrrrrrrrr','K2Node_CallFunction_0')]=='Get Forward Vector'
result={'pins_compared':len(before),'intentional_link_changes':changed,'unexpected_link_changes':0}
(out/'graph-verified.json').write_text(json.dumps(result,indent=2));print('Compared',len(before),'pins;',len(changed),'intended changes, zero unexpected changes.')
