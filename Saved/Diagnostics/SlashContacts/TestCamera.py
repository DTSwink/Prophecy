import unreal,json,pathlib,time,traceback,builtins
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
s={'events':[],'rows':[],'last':-1,'phase':0,'actors':[],'wall':time.perf_counter()}
builtins._attack_camera_test=s
def v(p):return [p.x,p.y,p.z]
def end(reason):
    unreal.unregister_slate_post_tick_callback(s['handle'])
    (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/Camera.json').write_text(json.dumps({'reason':reason,'events':s['events'],'rows':s['rows']}))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('ATTACK_CAMERA_TEST',reason,len(s['rows']))
def tick(dt):
    try:
        w=editor.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        if not s['actors']:
            s['actors']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
            s['pc']=unreal.GameplayStatics.get_player_controller(w,0);s['player']=unreal.GameplayStatics.get_player_pawn(w,0)
            s['other']=next(a for a in s['actors'] if a.get_actor_label()=='BP_ProphecyManualPoseAgent4')
            for a in s['actors']:a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
        if t>=8 and s['phase']==0:
            s['pc'].possess(s['other']);s['phase']=1;s['events'].append([t,'possess NPC'])
        if t>=12 and s['phase']==1:
            s['pc'].un_possess();s['phase']=2;s['events'].append([t,'unpossess'])
        if t>=14 and s['phase']==2:
            s['pc'].possess(s['player']);s['phase']=3;s['events'].append([t,'repossess player'])
        if t>=17 and s['phase']==3:
            for a in s['actors']:
                a.set_actor_tick_enabled(False);a.stop_nn_attack()
            s['phase']=4;s['events'].append([t,'stop attacks and automatic BP triggers'])
        for a in s['actors']:
            spring=a.get_agent_spring_arm();attack=a.get_nn_attack_state();mesh=a.get_pose_reference_mesh()
            s['rows'].append({'t':t,'actor':a.get_name(),'player':isinstance(a.get_controller(),unreal.PlayerController),'attack':str(attack[0]) if attack else None,'frame':attack[-1] if attack else 0,'spring':v(spring.get_world_location()),'offset':v(spring.get_editor_property('target_offset')),'pelvis':v(mesh.get_socket_location('pelvis')),'followers':len(a.get_components_by_class(unreal.ProphecyAttackCameraComponent))})
        if t>=20:end('Complete')
        elif time.perf_counter()-s['wall']>120:end('Timeout')
    except Exception:end(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('ATTACK_CAMERA_TEST_STARTED')
