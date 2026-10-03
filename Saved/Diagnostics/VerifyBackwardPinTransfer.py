import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
w=ed.get_editor_world()
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary'))
assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary:SetWalkPinningBackwardTransfer')
assert not api.call_method('SetWalkPinningBackwardTransfer',(None,True,1.))
print('BACKWARD_TRANSFER_REFLECTED')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
report=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/LiveLibraryDefaults.txt').read_text(encoding='utf-8-sig')
assert 'status=3 ' in report and 'other_values_and_wiring_preserved=1' in report,report
print(report)
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.WalkPinning')
