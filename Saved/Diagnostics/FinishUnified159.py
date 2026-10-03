import unreal,builtins,gc
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world() or ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Tempering.KneePlane 3')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 0')
s=getattr(builtins,'_calf_connection',None)
if s:s['rows']=[]
gc.collect()
print('KNEE_RECOVERY_TRIAL',unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Tempering.KneePlane'),'PLAY_ACTIVE',bool(ed.get_game_world()))
