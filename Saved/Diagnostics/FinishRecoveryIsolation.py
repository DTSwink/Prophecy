import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PLAY',bool(ed.get_game_world()))
for name in ('Prophecy.Recovery.PolePresentation','Prophecy.Tempering.PoleTrace','Prophecy.NNInputTraceFrames','Prophecy.Recovery.CleanSource','Prophecy.Recovery.PoleWindow','Prophecy.Tempering.PoleSmoothing'):
 print(name,unreal.SystemLibrary.get_console_variable_int_value(name))
