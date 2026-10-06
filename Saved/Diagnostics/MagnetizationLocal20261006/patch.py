import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
(p/'MagnetizationLocal20261006/graph.txt').write_bytes((p/'SwordThigh/BlueprintGraph.txt').read_bytes())
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.Compile')
print('LOCAL_SERVO_CORRECTION_COMPILING')