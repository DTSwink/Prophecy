import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PIE_ACTIVE',bool(ed.get_game_world()))
for c in ['Prophecy.UpperInertia.DebugResponse','Prophecy.UpperInertia.DebugNoTwist']:
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),c)
