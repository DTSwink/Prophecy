import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
cls = unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyUpperRootHorizonLibrary')
print(cls)
print(unreal.get_default_object(cls).call_method.__doc__)
unreal.SystemLibrary.execute_console_command(world, 'Automation RunTests Prophecy.NN.UpperRootHorizon.Resampling')
