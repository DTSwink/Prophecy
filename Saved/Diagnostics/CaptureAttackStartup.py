import unreal,builtins,pathlib,json,time,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play; startup test requires own session'
tag=sys.argv[1];p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'/('AttackStartup-'+tag+'.json')
s={'rows':[],'wall':time.perf_counter(),'last':None,'h':None,'actors':None,'start':None}
builtins._attack_startup=s
def done(reason):
 unreal.unregister_slate_post_tick_callback(s['h'])
 p.write_text(json.dumps({'reason':reason,'rows':s['rows']},indent=2))
 s['actors']=None
 if ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
 print('ATTACK_STARTUP_DONE',tag,reason,len(s['rows']))
def tick(dt):
 now=time.perf_counter();w=ed.get_game_world()
 if not w:
  if now-s['wall']>90:done('No world')
  return
 t=unreal.GameplayStatics.get_time_seconds(w)
 if t==s['last']:return
 s['last']=t
 if s['actors'] is None:s['actors']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
 if s['start'] is None:s['start']=t
 s['rows'].append({'t':t,'wall':now-s['wall'],'dt':dt,'states':[{ 'name':a.get_name(),'attack':str(a.get_nn_attack_state()),'tick':a.get_editor_property('tick debug')}for a in s['actors']]})
 if t-s['start']>=5:done('Complete')
 elif now-s['wall']>180:done('Timeout')
s['h']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('ATTACK_STARTUP_STARTED',tag)
