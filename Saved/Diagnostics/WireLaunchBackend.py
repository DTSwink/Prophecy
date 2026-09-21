import unreal, pathlib, shutil
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not e.get_game_world()
unreal.SystemLibrary.execute_console_command(e.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
saved=pathlib.Path(unreal.Paths.project_saved_dir())
shutil.copyfile(saved/'Diagnostics/SwordThigh/BlueprintGraph.txt',saved/'Diagnostics/LaunchBackendBefore.txt')
unreal.SystemLibrary.execute_console_command(e.get_editor_world(),'Prophecy.Debug.WireLaunchBackend')
unreal.SystemLibrary.execute_console_command(e.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
