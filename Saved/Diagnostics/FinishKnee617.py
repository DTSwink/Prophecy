import unreal,builtins,gc
s=getattr(builtins,'_calf_connection',None)
if s:s['rows']=[]
gc.collect()
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('KNEE_DIAGNOSTIC_FINISHED_PLAY',bool(ed.get_game_world()))
