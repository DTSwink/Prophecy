import pathlib,json
base=pathlib.Path(__file__).parent
def read(p):
    b=p.read_bytes()
    return b.decode('utf-16' if b.startswith(b'\xff\xfe') else 'utf-8-sig')
before=read(base/'KickRolePinsBefore.txt')
after=read(base/'SwordThigh/BlueprintGraph.txt')
def pins(text,node):
    block=next(b for b in text.split('\n\n') if ' | EventGraph | '+node+' | ' in b.split('\n')[0])
    return dict((line.strip().split('=',1)[0],line.strip().split('=',1)[1]) for line in block.splitlines()[1:] if '=' in line)
old=pins(before,'K2Node_CallFunction_170');new=pins(after,'K2Node_CallFunction_170')
for key,val in old.items():
    assert new[key]==val,(key,val,new[key])
for src,dst in [('FeetTranslation','NonKickingFootTranslationXY'),('FeetTranslationZ','NonKickingFootTranslationZ'),('FeetRotation','NonKickingFootRotation')]:
    assert new[src]==new[dst],(src,dst,new[src],new[dst])
assert pins(before,'K2Node_CallFunction_196')==pins(after,'K2Node_CallFunction_196')
print('All old kick-node pin defaults/links preserved; all 3 new non-kicking inputs match original shared inputs.')
(base/'KickRolePinValidation.json').write_text(json.dumps({'old_inputs_preserved':True,'non_kicking_inputs_inherit_shared':True,'tempering_node':'K2Node_CallFunction_170','recovery_node':'K2Node_CallFunction_196'},indent=2),encoding='utf-8')
