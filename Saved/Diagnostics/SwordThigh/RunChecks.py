import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.SwordFixture C:/Users/singerie/AppData/Local/Temp/ProphecyAttachedSword-20260913.json')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.Jolt.GenericJoint.KinematicFollowerContacts')
