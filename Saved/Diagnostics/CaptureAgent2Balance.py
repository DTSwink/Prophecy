import builtins,json,pathlib,time,traceback,unreal,sys
variant=sys.argv[1] if len(sys.argv)>1 else 'baseline'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
s=dict(owned=not bool(ed.get_game_world()),start=time.monotonic(),rows=[],last=-1,actor=None)
builtins._agent2_balance=s
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
smooth=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNRootWindowLibrary'))
def xyz(v):return [v.x,v.y,v.z]
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    filename='Agent2Balance.json' if variant=='baseline' else 'Agent2Balance_'+variant+'.json'
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics',filename).write_text(json.dumps(dict(reason=reason,variant=variant,actor=s.get('identity'),rows=s['rows'])))
    if s['owned'] and ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('AGENT2_BALANCE',reason)
def tick(_):
    try:
        if time.monotonic()-s['start']>100:finish('timeout');return
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        if s['actor'] is None:
            actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            s['actor']=next((a for a in actors if a.get_actor_label()=='BP_ProphecyManualPoseAgent2'),None)
            if s['actor'] is None:
                if t>2:raise RuntimeError('Target missing: '+str([(a.get_name(),a.get_actor_label()) for a in actors]))
                return
            a=s['actor'];s['identity']=dict(label=a.get_actor_label(),path=a.get_path_name(),handle=a.get_agent_handle().index)
            print('CAPTURING',s['identity'])
        a=s['actor']
        if t>5 and variant!='baseline' and not s.get('changed'):
            if variant=='disabled':assert lib.call_method('SetRootSelfBalancing',(a,False,600.,.05,2.,1.,30.,1.))
            elif variant=='input_one':assert lib.call_method('SetRootSelfBalancing',(a,True,600.,1.,2.,1.,30.,1.))
            elif variant=='smoothing_one':assert smooth.call_method('SetLocomotionRootWindowSmoothing',(a,1.,1.,1.))
            else:raise ValueError(variant)
            s['changed']=True
        window=a.get_locomotion_root_window()
        if window:
            enabled,active,target=lib.call_method('GetRootSelfBalancingState',(a,))
            roots,times=window
            inp=a.get_locomotion_input()
            feet={}
            for name in ['foot_l','foot_r']:
                b=a.get_physical_body_state(name)
                feet[name]=dict(p=xyz(b[0].translation),v=xyz(b[1]),sim=b[-1]) if b else None
            row=dict(time=t,enabled=enabled,active=active,target=xyz(target),feet=feet,
                root=xyz(a.get_root_low_point()),yaw=a.get_actor_rotation().yaw,mode=str(a.get_simulation_mode()),jolt=a.is_jolt_physical_animation_enabled(),
                smoothing=smooth.call_method('GetLocomotionRootWindowSmoothing',(a,)),
                input=xyz(inp.world_move_input),run=inp.run,speed_scale=inp.speed_scale,turn_scale=inp.turn_scale,
                velocity=xyz(a.get_root_velocity()[0]),roots=[xyz(r.translation) for r in roots])
            s['rows'].append(row)
        if t>30:finish('complete')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if s['owned']:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
