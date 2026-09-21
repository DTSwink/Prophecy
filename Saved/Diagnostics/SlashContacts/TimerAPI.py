import unreal
print([x for x in dir(unreal.SystemLibrary) if 'timer' in x.lower()])
print([x for x in dir(unreal.ProphecyAgent) if 'timer' in x.lower()])
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.Handoff.CarrierCoordinates')
