import unreal,builtins
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
for name in list(vars(builtins)):
 if name.startswith('_harness_knee_') or name=='_calf_connection':
  s=getattr(builtins,name)
  if isinstance(s,dict):
   for key in ('cb','h'):
    if s.get(key):
     try:unreal.unregister_slate_post_tick_callback(s[key])
     except Exception:pass
   if 'rows' in s:s['rows'].clear()
w=ed.get_game_world() or ed.get_editor_world()
for c in ('Prophecy.NNInputTraceFrames 0','Prophecy.Tempering.HarnessKnee 0','Prophecy.Tempering.HistoricalAudit 0','Prophecy.Recovery.CleanSource 0'):
 unreal.SystemLibrary.execute_console_command(w,c)
if ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
print('HARNESS_EXPERIMENTS_STOPPED')
