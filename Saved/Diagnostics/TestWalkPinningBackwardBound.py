import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('USER_PIE_ACTIVE',ed.get_game_world() is not None)
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary'))
assert lib.call_method('SetWalkPinningBackwardBound',args=(None,False,20.,60.,0)) is False
assert lib.call_method('DrawWalkPinningBackwardBound',args=(None,100.,2.)) is False
assert lib.call_method('SetWalkPinningCircleBound',args=(None,False,20.,60.,0)) is False
assert lib.call_method('DrawWalkPinningCircleBound',args=(None,2.)) is False
print('LINE_AND_CIRCLE_BOUND_NODES_REFLECTED')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.WalkPinning.BackwardBound+Prophecy.NN.WalkPinning.CircleBound+Prophecy.NN.WalkPinning.Smoothing')
