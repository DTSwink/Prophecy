import unreal,pathlib,time,json,traceback,sys
tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'
frames=int(sys.argv[2]) if len(sys.argv)>2 else 1200
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackPerformance';out.mkdir(exist_ok=True)
s=dict(start=time.monotonic(),last=None,frame=0,started=False,rows=[],settings={})
def tr(t):return [t.translation.x,t.translation.y,t.translation.z,t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    w=ed.get_game_world()
    if w:unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture stop')
    (out/(tag+'-poses.json')).write_text(json.dumps(dict(error=error,settings=s['settings'],rows=s['rows']),separators=(',',':')))
    print('ATTACK_PERFORMANCE_DONE',tag,error or 'complete',s['frame']);s['rows'].clear()
    if w:level.editor_request_end_play()
def tick(_):
    try:
        assert time.monotonic()-s['start']<150,'Capture timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['frame']+=1
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        if s['frame']==30:
            s['settings']=dict(mode=str(a.get_simulation_mode()),actors=len(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)),maxfps=unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS'))
            s['settings']['agents']=[dict(name=x.get_name(),handle=str(x.get_agent_handle()),inference=x.get_editor_property('bNNInferenceEnabled')) for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)]
            s['settings']['managers']=[dict(name=x.get_name(),crowd=x.get_editor_property('CrowdSize'),runtime=x.get_editor_property('PreferredRuntime')) for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyNNLocomotionManager)]
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture '+tag+' '+str(frames));s['started']=True
        # Separate exact-motion check; outside the native timed world interval.
        if 95<=s['frame']<=600:
            names,future,presented,alpha=a.read_nn_future_world_pose()
            s['rows'].append(dict(frame=s['frame'],state=str(a.get_nn_attack_state()),future=[tr(t) for t in future],presented=[tr(t) for t in presented],root=[a.get_root_low_point().x,a.get_root_low_point().y,a.get_root_low_point().z]))
        if s['frame']>=frames+31:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
