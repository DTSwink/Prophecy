import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.WalkPinning.CoordinateSpace+Prophecy.NN.WalkPinning.BackwardBound+Prophecy.NN.WalkPinning.CircleBound+Prophecy.NN.WalkPinning.Smoothing')
