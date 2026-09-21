import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('Sword phase test uses a separate transient world; no authored assets are changed.')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Jolt.Sword.AttackCollisionPhases')
