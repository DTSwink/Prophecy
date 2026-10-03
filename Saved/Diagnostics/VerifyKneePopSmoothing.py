import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyKneePopSmoothingLibrary'))
print('KNEE_NODE',lib,lib.call_method('SetKneePopSmoothing',args=(None,True,4.)))
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.PhysicalTargets.KneePopSmoothing+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.NN.PhysicalTargets.AttackLegClamps')
