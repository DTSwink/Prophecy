"""Explicit install/verify, with a fresh graph baseline and no unrelated saves."""
import hashlib, json, pathlib, shutil, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'User Play preserved'
root = pathlib.Path(unreal.Paths.project_dir())
out = root / 'Saved/Diagnostics/SwordOptimised'
bp = unreal.load_asset('/Game/_mygame/sword/A_Sword')
source = root / 'Content/_mygame/sword/A_Sword.uasset'
if not (out / 'A_Sword.before-optimised.uasset').exists():
    shutil.copy2(source, out / 'A_Sword.before-optimised.uasset')

def audit(name):
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Prophecy.Sword.AuditCollisionGraph')
    text = (root / 'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_text(encoding='utf-16')
    blocks = [b for b in text.split('\n\n') if '/Game/_mygame/sword/A_Sword' in b]
    (out / name).write_text('\n\n'.join(blocks), encoding='utf-8')
    return parse('\n\n'.join(blocks))

def parse(text):
    result = {}
    blocks = text.split('\n\n')
    for b in blocks:
        if not b.strip(): continue
        lines = b.strip().splitlines()
        _, graph, node, *_ = lines[0].split(' | ')
        for line in lines[1:]:
            pin = line.strip().split('=')[0]
            result[(graph,node,pin)] = line
    return result

before = parse((out / 'install-before.txt').read_text(encoding='utf-8')) if (out / 'install-before.txt').exists() else audit('install-before.txt')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Prophecy.Sword.InstallOptimised')
unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, 'Optimised', True)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
after = audit('install-after.txt')
assert any(k[1] == 'ProphecyStartOptimisedCut' for k in after), 'Installer did not run'
allowed = {
    ('EventGraph','K2Node_Knot_37','OutputPin'),
    ('EventGraph','K2Node_CallFunction_50','execute'),
    ('EventGraph','ProphecyPikeWoundCorrection','execute'),
    ('EventGraph','K2Node_AddComponent_0','ReturnValue'),
    ('handle cuts f','K2Node_FunctionEntry_0','then'),
    ('EventGraph','K2Node_Knot_25','OutputPin'),
    ('EventGraph','ProphecyPikeSkipRestore','execute'),
    ('EventGraph','K2Node_Knot_26','InputPin'),
}
old_target = before[('handle cuts f','K2Node_FunctionEntry_0','then')].split('->')[1].strip()
old_node, old_pin = old_target.split('.',1)
allowed.add(('handle cuts f', old_node, old_pin))
changes = [(k,old,after.get(k)) for k,old in before.items() if after.get(k) != old]
unexpected = [row for row in changes if row[0] not in allowed]
(out / 'graph-verification.json').write_text(json.dumps(dict(original_pins=len(before),
    changes=changes, unexpected=unexpected), indent=2), encoding='utf-8')
assert not unexpected, 'Unexpected graph changes: '+str(unexpected[:8])
cdo = unreal.get_default_object(bp.generated_class())
assert cdo.get_editor_property('Optimised')
print('Original pins verified:', len(before), 'changed:', len(changes))
print('Optimised CDO:', cdo.get_editor_property('Optimised'))
print('Installation verified; left unsaved pending motion tests')
