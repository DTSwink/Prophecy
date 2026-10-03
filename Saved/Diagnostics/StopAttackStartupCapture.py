import unreal,builtins
s=getattr(builtins,'_attack_startup',None)
if s and s.get('h'):
 unreal.unregister_slate_post_tick_callback(s['h']);s['h']=None
 unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
 print('Stopped owned startup capture')
