import builtins,json,unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
info={'world':str(world),'samplers':{}}
for key in ('_prophecy_camera_relative_hitch','_prophecy_pelvis_backward_capture'):
    state=getattr(builtins,key,None)
    if state:
        info['samplers'][key]={k:state.get(k) for k in ('path','done','error','first_t','last_t','experiment')}
        info['samplers'][key]['rows']=len(state.get('rows',[]))
if world:
    agent=unreal.GameplayStatics.get_player_pawn(world,0)
    info['delta_seconds']=unreal.GameplayStatics.get_world_delta_seconds(world)
    info['agent']=str(agent)
    if isinstance(agent,unreal.ProphecyAgent):
        info.update(mode=str(agent.get_simulation_mode()),jolt=agent.is_jolt_physical_animation_enabled(),
            pose_mesh=str(agent.get_pose_reference_mesh()),feedback=str(agent.get_physical_feedback_tolerance('pelvis')))
print(json.dumps(info,indent=2))
