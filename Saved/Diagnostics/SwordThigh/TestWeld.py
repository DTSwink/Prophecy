import time,unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.Jolt.GenericJoint.WeldedHandContacts')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.SwordFixture C:/Users/singerie/AppData/Local/Temp/ProphecyWeldedSword-'+str(int(time.time()))+'.json')
