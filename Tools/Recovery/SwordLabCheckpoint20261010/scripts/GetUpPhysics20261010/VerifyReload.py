import unreal,pathlib,shutil,json
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/GetUpPhysics20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
report=(out.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
print(report)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(out.parent/'SwordThigh/BlueprintGraph.txt',out/'graph-after.txt')
before=(out/'graph-before.txt').read_text(encoding='utf-16')
after=(out/'graph-after.txt').read_text(encoding='utf-16')
print('GRAPH_IDENTICAL',before==after)
assert before==after
print('BRIDGE',unreal.get_default_object(unreal.ProphecyJoltBodyDriveLibrary).call_method('NotifyArmsAntiJiggleGetUpWindow',(None,False)))
