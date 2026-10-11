"""Measure only the live holster sampler in owned PIE, outside motion captures."""
import unreal,pathlib,time,traceback,json
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world(),'Existing Play is left untouched'
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SwordOvernight20261011'
assert not (out/'geometry-benchmark.csv').exists(),'Preserve previous measurement'
state={'world':None,'start':time.monotonic()}
def finish(reason):
 unreal.unregister_slate_post_tick_callback(state['callback'])
 if state['world'] and editor.get_game_world()==state['world']:level.editor_request_end_play()
 (out/'geometry-benchmark-result.json').write_text(json.dumps({'reason':reason,'tick':state.get('tick')}))
 print('GEOMETRY_BENCH',reason)
def tick(_):
 try:
  if time.monotonic()-state['start']>60:return finish('timeout')
  world=editor.get_game_world()
  if not world:return
  state['world']=world
  player=unreal.GameplayStatics.get_player_pawn(world,0)
  if not isinstance(player,unreal.ProphecyAgent):return
  n=int(player.get_editor_property('absolute tick debug'))
  if n>=35:
   state['tick']=n
   unreal.SystemLibrary.execute_console_command(world,'Prophecy.Sword.BenchGeometry')
   assert (out/'geometry-benchmark.csv').exists()
   return finish('passed')
 except Exception:finish(traceback.format_exc())
state['callback']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
