import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.NonKickGuidance 0')
print('Family-based trial disabled; original guidance restored while preparing global geometry correction.')
