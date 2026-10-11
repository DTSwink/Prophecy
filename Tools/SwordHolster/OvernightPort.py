"""Apply the user-authorized current lab values; verify graph before saving."""
import unreal, pathlib, json, difflib, re
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SwordOvernight20261011'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);world=ed.get_editor_world()
assert not ed.get_game_world(), 'Existing Play is left untouched.'
assert not list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), 'Preserve unexpected edits first.'
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.RefreshSwordHolsterValues')
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Sword.AuditCollisionGraph')
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.LiveAgentTypes Inspect')
graph=root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt'
def read(p):
    raw=p.read_bytes();return raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
before=read(out/'before-graph.txt');after=read(graph)
def normalize(s):
    return re.sub(r'(MaxReachSpeed|MaxReachRotationSpeed)=\d+\.\d+',r'\1=<imported>',s)
assert normalize(before)==normalize(after), 'Graph changed beyond the two requested speed literals.'
assert 'MaxReachSpeed=230.0' in after and 'MaxReachRotationSpeed=600.0' in after
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
(out/'port-graph.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True))),encoding='utf-8')
(out/'after-graph.txt').write_text(after,encoding='utf-8')
print('PORT_VALUES_SAVED; only two speed literals changed; graph otherwise exact.')
