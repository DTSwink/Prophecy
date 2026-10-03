import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
for n in ('GetValidAttackTarget','SetAttackTargetExtraReach'):
 assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyAttackControlLibrary:'+n),n
print('Attack target nodes loaded; Play:',bool(ed.get_game_world()))
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackControlLibrary'))
result=api.call_method('GetValidAttackTarget',(None,unreal.Name('jabL'),unreal.Vector(1,2,3)))
assert len(result)==4 and result[3]==0.,result
print('Four outputs reflected; invalid agent distance to limit:',result[3])
assert not ed.get_game_world(),'Preserve current Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RefreshAttackTargetMargin')
pins=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/AttackTargetMarginPins.txt').read_text(encoding='utf-8-sig')
assert 'values_and_links_preserved=1' in pins,pins
print(pins)
# New functions in an existing native library can leave its older BP call nodes
# referencing archived CDOs. Validate the user's whole Blueprint, not just the new API.
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
report=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/LiveLibraryDefaults.txt').read_text(encoding='utf-8-sig')
assert 'status=3 ' in report and 'other_values_and_wiring_preserved=1' in report,report
print(report)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Attack.TargetReach')
