import unreal, pathlib, json, traceback, time
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
started_here=not bool(ed.get_game_world())
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttachedJoltMeshes'
folder.mkdir(parents=True,exist_ok=True)
s={'start':time.monotonic()}
def tick(_):
    try:
        assert time.monotonic()-s['start']<45,'PIE timeout'
        world=ed.get_game_world()
        if not world or unreal.GameplayStatics.get_time_seconds(world)<1:return
        agents=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent)
        assert len(agents)==3,len(agents)
        rows=[{'actor':a.get_name(),'jolt_enabled':a.is_jolt_physical_animation_enabled(),'jolt_selected':a.is_jolt_physical_animation_selected()} for a in agents]
        assert all(a['jolt_enabled'] and a['jolt_selected'] for a in rows),rows
        setups=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyJoltFightSetup)
        assert all(not a.get_editor_property('last_error') for a in setups)
        unreal.SystemLibrary.execute_console_command(world,'Prophecy.Jolt.MeshAudit BP_ProphecyManualPoseAgent')
        audit=json.loads((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/DefaultJoltMeshes/World.json').read_text(encoding='utf-8-sig'))
        cubes=[m for m in audit['meshes'] if m['component'].rsplit('.',1)[-1]=='Cube']
        assert len(cubes)==3 and all(m['jolt'] and m['jolt_dynamic'] and not m['chaos_simulating'] for m in cubes),cubes
        for a in agents:
            c=next(c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.get_name()=='Cube')
            assert c.get_attach_parent() is None,c.get_path_name()
        result={'result':'passed','agents':rows,'cubes':cubes}
    except Exception: result={'result':'failed','error':traceback.format_exc()}
    unreal.unregister_slate_post_tick_callback(s['cb'])
    (folder/'PIE.json').write_text(json.dumps(result,indent=2))
    if started_here: unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('ATTACHED_JOLT_MESHES',result['result'])
s['cb']=unreal.register_slate_post_tick_callback(tick)
if started_here: unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
