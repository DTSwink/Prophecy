import builtins,json,pathlib,time,traceback,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
s=dict(owned=not bool(ed.get_game_world()),start=time.monotonic(),rows=[],last=-1)
builtins._capture_balance_window=s
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
smooth=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNRootWindowLibrary'))
def xyz(v):return [v.x,v.y,v.z]
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/BalanceWindowCapture.json').write_text(json.dumps(dict(reason=reason,rows=s['rows'])))
    if s['owned'] and ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(_):
    try:
        if time.monotonic()-s['start']>40:finish('timeout');return
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        window=a.get_locomotion_root_window()
        if window:
            enabled,active,target=lib.call_method('GetRootSelfBalancingState',(a,))
            roots,times=window
            s['rows'].append(dict(time=t,enabled=enabled,active=active,target=xyz(target),
                smoothing=smooth.call_method('GetLocomotionRootWindowSmoothing',(a,)),
                velocity=xyz(a.get_root_velocity()[0]),roots=[xyz(r.translation) for r in roots]))
        if t>7:finish('complete')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if s['owned']:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
