import unreal,builtins,gc
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve active Play'
for name in ('_attack_startup','_calf_connection'):
 s=getattr(builtins,name,None)
 if isinstance(s,dict):
  s['actors']=None;s.get('rows',[]).clear()
gc.collect()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'obj gc')
print('Released completed captures and requested editor garbage collection')
