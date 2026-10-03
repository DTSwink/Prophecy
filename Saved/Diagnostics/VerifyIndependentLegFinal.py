import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LiveAgentTypes-Inspect.txt'
print(p.read_text())
for n in ('Prophecy.Recovery.CleanSource','Prophecy.Recovery.PoleWindow','Prophecy.Recovery.LocomotionLengthTarget','Prophecy.Tempering.PoleTrace','Prophecy.NNInputTraceFrames'):
 print(n,unreal.SystemLibrary.get_console_variable_int_value(n))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.LowerTempering.IndependentRecoveryClock+Prophecy.Joints.CalfReturnLocomotionTarget')
