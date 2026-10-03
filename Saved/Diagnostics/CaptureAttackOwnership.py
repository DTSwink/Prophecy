import unreal,pathlib,time,json,traceback,sys,math
tag=sys.argv[1];optimized=int(sys.argv[2]);isolated=int(sys.argv[3]) if len(sys.argv)>3 else 0
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackPerformance';out.mkdir(exist_ok=True)
s=dict(start=time.monotonic(),last=None,frame=0,rows=[],events=[],actors=[])
command='Prophecy.Attack.SkipOverwrittenLocomotion '
old=unreal.SystemLibrary.get_console_variable_int_value(command.strip())
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),command+str(optimized))
cases=[('overL',False,[]),('hookL',True,[]),('slashR',False,[(8,True)]),('pike',True,[(8,False)]),('overR',False,[(8,True),(14,False)]),('headbutt',True,[(8,False),(14,True)])]
def tr(t):return [t.translation.x,t.translation.y,t.translation.z,t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    w=ed.get_game_world()
    if w:unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture stop')
    unreal.SystemLibrary.execute_console_command(w or ed.get_editor_world(),command+str(old))
    (out/(tag+'-poses.json')).write_text(json.dumps(dict(error=error,events=s['events'],rows=s['rows']),separators=(',',':')))
    print('ATTACK_OWNERSHIP_DONE',tag,error or 'complete',s['frame']);s['rows'].clear();s['actors'].clear();s.pop('player',None)
    if w:level.editor_request_end_play()
def tick(dt):
    try:
        assert time.monotonic()-s['start']<150,'Capture timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['frame']+=1
        f=s['frame']
        if f==30:
            s['actors']=sorted(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent),key=lambda a:a.get_agent_handle().index)
            s['player']=unreal.GameplayStatics.get_player_pawn(w,0)
            for a in s['actors']:
                a.set_actor_tick_enabled(False);a.stop_nn_attack();a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
                if isolated and a!=s['player']:a.set_editor_property('bNNInferenceEnabled',False)
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture '+tag+' 1120')
        if not s['actors']:return
        a=s['player']
        for actor in s['actors']:actor.apply_nn_pose_kinematically(dt)
        case=(f-60)//180;offset=(f-60)%180
        if 0<=case<len(cases):
            family,half,switches=cases[case]
            if offset==0:
                a.stop_nn_attack()
                names,pose,_,_=a.read_nn_future_world_pose();pelvis=pose[[str(n) for n in names].index('pelvis')].translation
                s['target']=pelvis+unreal.Vector(-30,90,30)
                a.set_locomotion_input(unreal.Vector(1,0,0),False,unreal.Vector(0,1,0),1.,1.)
                assert a.trigger_nn_attack(family,s['target'],half),family
                s['events'].append(dict(frame=f,event='start',family=family,half=half))
            for at,half in switches:
                if offset==at:
                    assert a.get_nn_attack_state(),'Attack ended before switch'
                    assert a.set_nn_half_attack_enabled(half)
                    s['events'].append(dict(frame=f,event='switch',half=half))
            if offset==10:
                s['target']=s['target']+unreal.Vector(70,170,15)
                state=a.get_nn_attack_state();assert state
                assert a.set_nn_attack_target(s['target']);assert state==a.get_nn_attack_state()
            if offset==65:a.stop_nn_attack()
            state=a.get_nn_attack_state()
            if state:
                assert all((v-s['target']).length()<.001 for v in a.get_nn_attack_target())
            actors=[]
            for actor in s['actors']:
                names,future,presented,alpha=actor.read_nn_future_world_pose()
                values=[tr(t) for t in future]
                assert all(math.isfinite(x) for row in values for x in row)
                actors.append(dict(state=str(actor.get_nn_attack_state()),future=values,presented=[tr(t) for t in presented],root=tr(actor.get_actor_transform())))
            s['rows'].append(dict(frame=f,actors=actors))
        if f>=1151:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
