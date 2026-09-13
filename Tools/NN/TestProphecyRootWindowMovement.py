import builtins,json,pathlib,time,traceback,math,unreal
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not e.get_game_world()
s=dict(start=time.monotonic(),last=-1,n=0,rows=[],advance_error=0.)
builtins._root_movement_test=s
c=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNRootWindowLibrary'))
def setf(a,d,r,o):assert c.call_method('SetLocomotionRootWindowSmoothing',(a,d,r,o))
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    data={k:v for k,v in s.items() if k in ['n','rows','advance_error','idle_drift','idle_yaw_drift','released_distance']};data['reason']=reason
    (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootWindowMovement.json').write_text(json.dumps(data))
    if e.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('ROOT_WINDOW_MOVEMENT',reason)
def tick(_):
    try:
        if time.monotonic()-s['start']>90:finish('timeout');return
        w=e.get_game_world()
        if not w:return
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['n']+=1;n=s['n']
        if n==10:
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            a.set_actor_tick_enabled(False)
            setf(a,0,0,0)
            a.set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(0,1,0))
        if n<12:return
        roots,times=a.get_locomotion_root_window();p=roots[1].translation;y=roots[1].rotation.rotator().yaw
        row=dict(n=n,t=t,p=[p.x,p.y,p.z],yaw=y,speed=a.get_locomotion_state()[0].length())
        s['rows'].append(row)
        if n==12:s['idle']=p;s['idle_yaw']=y
        if n==160:
            s['idle_drift']=(p-s['idle']).length();s['idle_yaw_drift']=abs((y-s['idle_yaw']+180)%360-180)
            assert s['idle_drift']<.001 and s['idle_yaw_drift']<.001, 'All-zero idle must not move or turn'
            assert row['speed']<.001
            setf(a,.3,.4,.5)
        if 166<=n<245:
            if 'prev' in s and (p-s['prev'][0]).length()>.00001:
                error=(p-s['prev'][1]).length()
                s['advance_error']=max(s['advance_error'],error)
                assert error<.01, ('Root0 did not advance to filtered root1',error)
            s['prev']=(p,roots[2].translation)
        if n==245:
            s['released_distance']=(p-s['idle']).length()
            assert s['released_distance']>30, 'Partial factors must resume movement'
            setf(a,1,1,1)
        if n>=280:
            assert tuple(c.call_method('GetLocomotionRootWindowSmoothing',(a,)))==(1.,1.,1.)
            assert row['speed']>100
            finish('complete')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
