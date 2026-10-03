import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('RUN_BOOST_REFLECTION',unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary')).call_method('SetRunPinningBoost',args=(None,0.0)))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.RunPinning.HighestBoost+Prophecy.NN.WalkPinning')
print('RUN_BOOST_TESTS_QUEUED')
