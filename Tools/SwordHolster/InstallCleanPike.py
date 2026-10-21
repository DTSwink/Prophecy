"""Install the acceptance node without changing any authored conditions or joint pins."""
import json, pathlib, re, sys, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'User Play left untouched'
out = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/CleanPike'
out.mkdir(parents=True, exist_ok=True)
bp = unreal.load_asset('/Game/_mygame/sword/A_Sword')
def export(name):
    t = unreal.AssetExportTask()
    t.object, t.filename = bp, str(out / name)
    t.exporter = unreal.ObjectExporterT3D()
    t.automated, t.prompt, t.replace_identical = True, False, True
    assert unreal.Exporter.run_asset_export_task(t)
def pins(name):
    text = (out / name).read_text(encoding='utf-8')
    graphs = set(re.findall(r'^   (?:FunctionGraphs|UbergraphPages|MacroGraphs)\(\d+\)="[^\'\n]+\'([^\']+)\'"', text, re.M))
    stack, result = [], {}
    for line in text.splitlines():
        if re.match(r'\s*Begin Object ', line): stack.append(re.search(r'\bName="([^"]+)"', line).group(1))
        elif line.strip() == 'End Object': stack.pop()
        elif 'CustomProperties Pin ' in line and len(stack)>1 and stack[1] in graphs:
            result[tuple(stack[1:])+(re.search(r'PinId=(\w+)',line).group(1),)] = line.strip()
    return graphs, result
export('before.txt')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Prophecy.Editor.RefreshHolsterGripPins CleanPike')
export('after.txt')
graphs, before = pins('before.txt')
after_graphs, after = pins('after.txt')
assert graphs == after_graphs and not before.keys()-after.keys()
allowed = {
    ('K2Node_Event_0','then'), ('K2Node_CallFunction_154','execute'),
    ('K2Node_IfThenElse_5','then'), ('K2Node_Knot_6','InputPin'),
    ('K2Node_VariableSet_5','execute'), ('K2Node_CallFunction_105','execute'),
    ('K2Node_Knot_25','OutputPin'), ('K2Node_Knot_26','InputPin'),
    ('K2Node_VariableGet_44','sword'), ('K2Node_VariableGet_22','temp pike'),
}
changed = []
for key, old in before.items():
    new = after[key]
    if old == new: continue
    name = re.search(r'PinName="([^"]+)"',old).group(1)
    assert key[0]=='EventGraph' and (key[-2],name) in allowed,(key,name)
    strip_links=lambda s: re.sub(r'LinkedTo=\([^)]*\),','',s)
    assert strip_links(old)==strip_links(new),(key,name,'non-link mutation')
    changed.append([key[-2],name])
added = sorted({key[-2] for key in after.keys()-before.keys()})
assert added==sorted(['ProphecyEnableCleanPike','ProphecyAcceptPike','ProphecyPikeAccepted','ProphecyPikeSkipRestore']),added
result={'graphs':len(graphs),'preserved_pins':len(before),'changed_links':changed,'added_nodes':added,
        'conditions_and_tuning_preserved':True,'joint_pins_preserved':True,'saved':False}
(out/'graph-check.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
if '--save' in sys.argv:
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    print('CLEAN_PIKE_SAVED')
