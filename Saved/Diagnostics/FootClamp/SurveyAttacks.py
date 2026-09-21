import unreal, builtins, pathlib, json, time, traceback, sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts'
p.mkdir(exist_ok=True)
label=sys.argv[1] if len(sys.argv)>1 else 'before'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
s={'rows':[],'events':[],'wall':time.perf_counter(),'last':None,'actors':[],'phase':0}
builtins._slash_contact_survey=s
def v(x):return [x.x,x.y,x.z]
def tr(x):return {'p':v(x.translation),'q':[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w]}
def done(reason):
    unreal.unregister_slate_post_tick_callback(s['handle'])
    (p/(label+'.json')).write_text(json.dumps({'reason':reason,'events':s['events'],'rows':s['rows']}))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('SLASH_CONTACT_SURVEY_DONE',reason,len(s['rows']))
def tick(dt):
    try:
        w=editor.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        if not s['actors']:
            s['actors']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
            for a in s['actors']:
                if label=='kinematic':
                    assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
                spring=a.get_agent_spring_arm()
                s['events'].append({'actor':a.get_name(),'label':a.get_actor_label(),'location':v(a.get_actor_location()),'mesh_world':tr(a.get_pose_reference_mesh().get_world_transform()),'player':isinstance(a.get_controller(),unreal.PlayerController),'spring_parent':str(spring.get_attach_parent()) if spring else None,'spring_relative':v(spring.get_editor_property('relative_location')) if spring else None})
                if isinstance(a.get_controller(),unreal.PlayerController):
                    unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceAgent '+str(a.get_agent_handle().index))
                    unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceFrames 1200')
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
                if a.get_actor_label()=='Floor':s['events'].append({'floor':a.get_actor_label(),'transform':tr(a.get_actor_transform()),'bounds':str(a.get_actor_bounds(False))})
        managers=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyNNLocomotionManager))
        if label=='kinematic' and t<0.2:
            for m in managers:
                m.set_editor_property('clamp_foot',False)
                m.set_editor_property('clamp_calf',False)
        if t>=20 and s['phase']==0:
            for m in managers:
                m.set_editor_property('clamp_foot',False)
                m.set_editor_property('clamp_calf',False)
            s['phase']=1
            s['events'].append({'t':t,'action':'Disable foot and calf clamps on transient PIE manager'})
        for a in s['actors']:
            attack=a.get_nn_attack_state()
            if not attack:continue
            pose=a.read_nn_future_world_pose()
            if not pose:continue
            names,future,shown,alpha=pose; lookup={str(n):i for i,n in enumerate(names)}
            mesh=a.get_pose_reference_mesh();spring=a.get_agent_spring_arm()
            row={'t':t,'actor':a.get_name(),'attack':str(attack[0]),'frame':attack[-1],'half':attack[1],'phase':s['phase'],'mode':str(a.get_simulation_mode()),'root':v(a.get_actor_location()),'spring':v(spring.get_world_location()) if spring else None,'target_offset':v(spring.get_editor_property('target_offset')) if spring else None,'bones':{}}
            for bone in ['pelvis','calf_l','calf_r','foot_l','foot_r','ball_l','ball_r']:
                row['bones'][bone]={'mesh':tr(mesh.get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_WORLD))}
                if bone in lookup:row['bones'][bone].update({'future':tr(future[lookup[bone]]),'shown':tr(shown[lookup[bone]])})
            s['rows'].append(row)
        if t>=40:done('Complete')
        elif time.perf_counter()-s['wall']>180:done('Timeout')
    except Exception:done(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('SLASH_CONTACT_SURVEY_STARTED')
