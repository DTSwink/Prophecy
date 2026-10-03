import unreal,builtins,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Requires an owned diagnostic Play session'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackStartInertiaLibrary'))
s={'last':None,'wall':time.monotonic(),'h':None,'actor':None,'armed':False,'triggered':False,'rows':[],'capture':0}
builtins._foot_entry_probe=s
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FootEntryInertia-runtime.json'
def tr(x):return {'p':[x.translation.x,x.translation.y,x.translation.z],'q':[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w]}
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['h'])
    out.write_text(json.dumps({'reason':reason,'rows':s['rows']}),encoding='utf-8')
    print('ATTACK_START_PROBE_FINISHED',reason,len(s['rows']))
    if ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    s['actor']=None
    if getattr(builtins,'_foot_entry_probe',None) is s:del builtins._foot_entry_probe
def tick(dt):
    try:
        w=ed.get_game_world()
        if not w:
            if time.monotonic()-s['wall']>30:finish('No world')
            return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        if s['actor'] is None:
            s['actor']=next((a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.is_player_controlled()),None)
        a=s['actor']
        if a is None:return
        if not s['armed'] and t>=.5:
            a.set_actor_tick_enabled(False)
            a.stop_nn_attack()
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            assert lib.call_method('SetAttackStartPelvisInertia',args=(a,True,5,1.,7,1.,5,1.,7,1.))
            s['armed']=True
        target=a.get_authored_body_world_target('pelvis')
        if target:
            mesh=next(m for m in a.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name()=='PhysicalMesh')
            row={'t':t,'triggered':s['triggered'],'target':tr(target[2]),'previous':tr(target[0]),'future':tr(target[1]),'alpha':target[3],
                 'physical':tr(mesh.get_socket_transform('pelvis',unreal.RelativeTransformSpace.RTS_WORLD)),
                 'state':str(a.get_nn_attack_state())}
            row['bones']={}
            for bone in ['foot_l','foot_r','calf_l','calf_r','thigh_l','thigh_r','ball_l','ball_r']:
                bt=a.get_authored_body_world_target(bone)
                row['bones'][bone]={'target':tr(bt[2]),'physical':tr(mesh.get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_WORLD))}
            s['rows'].append(row)
        if s['armed'] and not s['triggered'] and t>=1.2:
            a.stop_nn_attack()
            location=a.get_actor_location()+a.get_actor_forward_vector()*150+unreal.Vector(0,0,60)
            assert a.trigger_nn_attack('overL',location,False,None)
            s['triggered']=True
            print('ATTACK_START_PROBE_TRIGGER',t)
        elif s['triggered']:
            s['capture']+=1
            if s['capture']>=16:finish('Complete')
        if time.monotonic()-s['wall']>120:finish('Timeout')
    except Exception:finish(traceback.format_exc())
s['h']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('ATTACK_START_PROBE_BEGUN')
