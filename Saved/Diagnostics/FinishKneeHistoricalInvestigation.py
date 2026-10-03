import unreal,builtins
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
for command in ('Prophecy.NNInputTraceFrames 0','Prophecy.Tempering.KneePlane 3','Prophecy.Recovery.CleanSource 1','Prophecy.Tempering.RaisedSource 0','Prophecy.Tempering.HistoricalAudit 0','Prophecy.Recovery.KneeReference 0'):
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),command)
for name in dir(builtins):
 if name.startswith(('_knee_historical','_knee_raised_source')) or name=='_calf_connection':
  value=getattr(builtins,name)
  if isinstance(value,dict) and isinstance(value.get('rows'),list):value['rows'].clear()
print('KNEE_INVESTIGATION_FINISHED','PIE',bool(ed.get_game_world()))
