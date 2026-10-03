import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
def lib(n): return unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.'+n))
clock=lib('ProphecyAgentTimeLibrary'); root=lib('ProphecyRootPhysicsLibrary')
rows=[]
if w:
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  if not a.has_valid_agent_handle(): continue
  row=dict(name=a.get_name(),rate=clock.call_method('GetAgentTimeDilation',(a,)),auto_run=root.call_method('GetLocomotionAutoRunSpeedThreshold',(a,)),walk_threshold=a.get_locomotion_walk_checkpoint_speed_threshold(),state=str(a.get_locomotion_state()),target=str(a.get_locomotion_target()),velocity=str(a.get_root_velocity()))
  rows.append(row)
print('TIME_GAIT',json.dumps(dict(play=bool(w),agents=rows)))
