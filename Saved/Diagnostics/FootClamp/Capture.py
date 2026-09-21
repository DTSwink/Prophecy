import unreal, builtins, pathlib, json, time, traceback, math
out = pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FootClamp'
out.mkdir(exist_ok=True)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
state={'wall':time.perf_counter(),'rows':[],'events':[],'last':None,'changed':False,'actors':[]}
builtins._foot_clamp_probe=state
def vec(v): return [v.x,v.y,v.z]
def gap(calf,foot,ref):
    end=unreal.MathLibrary.transform_location(calf,ref)
    return (end-foot.translation).length()
def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    (out/'Capture.json').write_text(json.dumps({'reason':reason,'events':state['events'],'rows':state['rows']}))
    print('FOOT_CLAMP_DONE',reason,len(state['rows']))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(dt):
    try:
        if time.perf_counter()-state['wall']>180: finish('Timeout');return
        w=editor.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==state['last']:return
        state['last']=t
        managers=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyNNLocomotionManager))
        if int(t)!=state.get('second'):
            state['second']=int(t)
            state['events'].append({'t':t,'settings':[dict(name=m.get_name(),foot=m.get_editor_property('clamp_foot'),calf=m.get_editor_property('clamp_calf'),foot_multiplier=m.get_editor_property('foot_clamp_length_multiplier'),calf_multiplier=m.get_editor_property('calf_clamp_length_multiplier')) for m in managers],'attacks':[{a.get_name():str(a.get_nn_attack_state())} for a in state['actors']]})
        if not state['actors']:
            state['actors']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
            if state['actors']:
                state['events'].append({'t':t,'managers':[dict(name=m.get_name(),foot=m.get_editor_property('clamp_foot'),calf=m.get_editor_property('clamp_calf'),foot_multiplier=m.get_editor_property('foot_clamp_length_multiplier'),calf_multiplier=m.get_editor_property('calf_clamp_length_multiplier')) for m in managers]})
        if t>=25 and not state['changed']:
            for m in managers:
                m.set_editor_property('clamp_calf',True)
                m.set_editor_property('calf_clamp_length_multiplier',1.0)
            state['changed']=True
            state['events'].append({'t':t,'action':'Enable Clamp Calf, multiplier 1 on transient PIE manager'})
        for a in state['actors']:
            pose=a.read_nn_future_world_pose()
            mesh=a.get_pose_reference_mesh()
            if not pose or not mesh:continue
            names,future,presented,alpha=pose;lookup={str(n):i for i,n in enumerate(names)}
            for side in ['l','r']:
                foot='foot_'+side;calf='calf_'+side
                if foot not in lookup or calf not in lookup:continue
                ref=mesh.get_ref_pose_position(mesh.get_bone_index(foot))
                f,c=future[lookup[foot]],future[lookup[calf]]
                pf,pc=presented[lookup[foot]],presented[lookup[calf]]
                mc=mesh.get_socket_transform(calf,unreal.RelativeTransformSpace.RTS_WORLD)
                mf=mesh.get_socket_transform(foot,unreal.RelativeTransformSpace.RTS_WORLD)
                state['rows'].append({'t':t,'changed':state['changed'],'actor':a.get_name(),'mode':str(a.get_simulation_mode()),'mesh':mesh.get_name(),'side':side,'reference_length':ref.length(),'future_length':(f.translation-c.translation).length(),'future_gap':gap(c,f,ref),'presented_gap':gap(pc,pf,ref),'mesh_gap':gap(mc,mf,ref),'alpha':alpha})
        if t>=50:finish('Complete')
    except Exception: finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('FOOT_CLAMP_STARTED')
