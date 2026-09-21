import unreal
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PIE',bool(e.get_game_world()))
print('DIRTY',[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()])
unreal.SystemLibrary.execute_console_command(e.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
