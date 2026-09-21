import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
c=unreal.get_default_object(unreal.load_class(None,'/Script/ProphecyJolt.ProphecyJoltContactSettingsLibrary'))
print('SLOP_REFLECTION_DEFAULT',c.call_method('GetJoltPenetrationSlop',(ed.get_editor_world(),)))
print('SLOP_REFLECTION_EDITOR_REJECTED',c.call_method('SetJoltPenetrationSlop',(ed.get_editor_world(),0.1)))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Jolt.ContactSettings.PenetrationSlop')

