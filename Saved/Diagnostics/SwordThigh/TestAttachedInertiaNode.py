import pathlib,time,unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
cdo=unreal.get_default_object(unreal.ProphecyAgent)
assert hasattr(cdo,'set_sword_attached_inertia_scale')
assert cdo.get_sword_attached_inertia_scale()==1.0
print('Attached inertia Blueprint setter/getter available; default=1')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.Jolt.GenericJoint.WeldedHandContacts')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.SwordFixture C:/Users/singerie/AppData/Local/Temp/ProphecyAttachedInertia-'+str(int(time.time()))+'.json')
