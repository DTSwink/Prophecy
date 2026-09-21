import unreal, json, pathlib, traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJoltStaticMeshLibrary'))
state=dict(phase=0,frames=0,rows=[],meshes=[])
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LaunchBackend/PIE.json'
out.parent.mkdir(parents=True,exist_ok=True)
def active(mesh):return lib.call_method('IsJoltStaticMeshPhysicsEnabled',args=(mesh,))
def launch(pawn):
    before={m.get_path_name() for m in pawn.get_components_by_class(unreal.StaticMeshComponent)}
    pawn.call_method('launch ball debug',args=(.1,2.0,.1))
    added=[m for m in pawn.get_components_by_class(unreal.StaticMeshComponent) if m.get_path_name() not in before]
    assert len(added)==1, 'Original function must spawn exactly one cube'
    state['meshes'].extend(added)
    return added[0]
def finish(result):
    unreal.unregister_slate_post_tick_callback(state['callback'])
    out.write_text(json.dumps(dict(result=result,rows=state['rows']),indent=2))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('LAUNCH_BACKEND_TEST',result)
def tick(_):
    try:
        w=ed.get_game_world()
        if not w:return
        state['frames']+=1
        assert state['frames']<600,'Timed out waiting for backend'
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t<.5:return
        pawn=unreal.GameplayStatics.get_player_pawn(w,0)
        assert pawn and isinstance(pawn,unreal.ProphecyAgent)
        if state['phase']==0:
            assert pawn.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
            assert pawn.enable_jolt_physical_animation()
            state['phase']=1
        elif state['phase']==1 and pawn.is_jolt_physical_animation_enabled():
            mesh=launch(pawn)
            state['start']=mesh.get_world_location()
            state['launch_frame']=state['frames'];state['phase']=2
        elif state['phase']==2 and state['frames']-state['launch_frame']>=5:
            mesh=state['meshes'][-1]
            assert active(mesh) and not mesh.is_simulating_physics()
            distance=(mesh.get_world_location()-state['start']).length()
            assert distance>0,'Jolt projectile must advance'
            state['rows'].append(dict(backend='Jolt',native=True,chaos=False,moved_cm=distance))
            mesh.destroy_component(pawn)
            pawn.disable_jolt_physical_animation()
            state['phase']=3
        elif state['phase']==3:
            assert not pawn.is_jolt_physical_animation_enabled()
            mesh=launch(pawn)
            assert not active(mesh) and mesh.is_simulating_physics()
            state['start']=mesh.get_world_location()
            state['launch_frame']=state['frames'];state['phase']=4
        elif state['phase']==4 and state['frames']-state['launch_frame']>=5:
            mesh=state['meshes'][-1]
            distance=(mesh.get_world_location()-state['start']).length()
            assert distance>0,'Chaos projectile must advance'
            state['rows'].append(dict(backend='Chaos',native=False,chaos=True,moved_cm=distance))
            mesh.destroy_component(pawn)
            finish('passed')
    except Exception:finish(traceback.format_exc())
state['callback']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
