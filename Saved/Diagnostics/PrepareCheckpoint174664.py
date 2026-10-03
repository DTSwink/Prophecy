import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PIE_ACTIVE',ed.get_game_world() is not None)
if ed.get_game_world() is None:
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.ClearAttackCache')
print('READY')
