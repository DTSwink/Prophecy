import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
s={'start':time.monotonic()};folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RandomStreamSeed'
def tick(dt):
 w=ed.get_game_world()
 if not w:return
 if unreal.GameplayStatics.get_time_seconds(w)<.25:return
 try:
  rows=[]
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   r=a.get_editor_property('Random Stream debug')
   rows.append(dict(actor=a.get_name(),initial_seed=r.initial_seed))
  assert rows and all(r['initial_seed']==100 for r in rows),rows
  seq={}
  for seed in [100,101]:
   r=unreal.RandomStream(initial_seed=seed);r.reset()
   seq[str(seed)]=[r.random_int_in_range(0,100000) for _ in range(5)]
  assert seq['100']!=seq['101']
  result=dict(result='passed',runtime=rows,independent_sequences=seq)
 except Exception:result=dict(result='failed',error=traceback.format_exc())
 unreal.unregister_slate_post_tick_callback(s['handle']);level.editor_request_end_play()
 (folder/'PIE.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
s['handle']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
