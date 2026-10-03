import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Do not duplicate Play'
w=ed.get_editor_world()
for command in ('Prophecy.NNInputTraceFrames 0','Prophecy.Tempering.HistoricalAudit 0','Prophecy.Tempering.HarnessKnee 0','Prophecy.Recovery.CleanSource 0'):
 unreal.SystemLibrary.execute_console_command(w,command)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('FIRST_SEPTEMBER20_VERSION_PLAY_REQUESTED_NO_CAPTURE')
