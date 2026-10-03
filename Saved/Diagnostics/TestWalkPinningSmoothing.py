import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('USER_PIE_ACTIVE',ed.get_game_world() is not None)
lib=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary')
assert lib,'Canonical library missing'
assert unreal.get_default_object(lib).call_method('SetWalkPinningSmoothing',args=(None,False,3,3)) is False
print('SMOOTHING_NODE_REFLECTED')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.WalkPinning.Smoothing')
