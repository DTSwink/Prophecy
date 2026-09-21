import unreal, pathlib, json, traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/DefaultJoltMeshes'
folder.mkdir(parents=True,exist_ok=True)
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJoltStaticMeshLibrary'))
standard=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJoltStandardPhysicsLibrary'))
s={'frame':0,'phase':0,'rows':[],'created':[]}
def finish(result):
    unreal.unregister_slate_post_tick_callback(s['callback'])
    for mesh in s['created']:
        try: mesh.destroy_component(mesh.get_owner())
        except Exception: pass
    (folder/'PIE.json').write_text(json.dumps({'result':result,'checks':s['rows']},indent=2))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('DEFAULT_JOLT_MESH_TEST',result)
def tick(_):
    try:
        s['frame']+=1
        assert s['frame']<500,'Timed out waiting for PIE'
        world=ed.get_game_world()
        if not world or unreal.GameplayStatics.get_time_seconds(world)<.4:return
        pawn=unreal.GameplayStatics.get_player_pawn(world,0)
        assert pawn
        if s['phase']==0:
            unreal.SystemLibrary.execute_console_command(world,'Prophecy.Jolt.MeshAudit BP_ProphecyManualPoseAgent')
            audit=json.loads((folder/'World.json').read_text(encoding='utf-8-sig'))
            cubes=[m for m in audit['meshes'] if m['component'].rsplit('.',1)[-1]=='Cube']
            assert cubes,'No current Cube components found'
            assert not audit['scene_error'],audit['scene_error']
            assert all(m['jolt'] for m in cubes),cubes
            s['rows'].append({'current_cubes':cubes})
            before={m.get_path_name() for m in pawn.get_components_by_class(unreal.StaticMeshComponent)}
            pawn.call_method('launch ball debug',args=(.1,2.0,.1))
            added=[m for m in pawn.get_components_by_class(unreal.StaticMeshComponent) if m.get_path_name() not in before]
            assert len(added)==1,'Launch function did not create one mesh'
            s['created']=added;s['launch_frame']=s['frame'];s['phase']=1
        elif s['phase']==1 and s['frame']-s['launch_frame']>=6:
            mesh=s['created'][0]
            native=lib.call_method('IsJoltStaticMeshPhysicsEnabled',args=(mesh,))
            simulated=standard.call_method('IsSimulatingPhysics',args=(mesh,unreal.Name('None')))
            assert native and simulated and not mesh.is_simulating_physics(),(native,simulated,mesh.is_simulating_physics())
            s['rows'].append({'launched_mesh':mesh.get_path_name(),'jolt':native,'standard_simulation_getter':simulated,'chaos_simulating':False})
            finish('passed')
    except Exception: finish(traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
