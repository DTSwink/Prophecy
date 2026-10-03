import builtins,json,pathlib,time,traceback,unreal,sys
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not e.get_game_world()
s=dict(start=time.monotonic(),last=-1,n=0,rows=[])
builtins._idle_root_audit=s
c=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNRootWindowLibrary'))
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    name=sys.argv[1] if len(sys.argv)>1 else 'RootIdleBefore'
    (pathlib.Path(unreal.Paths.project_saved_dir())/('Diagnostics/'+name+'.json')).write_text(json.dumps(dict(reason=reason,rows=s['rows'])))
    if e.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('ROOT_IDLE_AUDIT',reason)
def tick(_):
    try:
        if time.monotonic()-s['start']>70:finish('timeout');return
        w=e.get_game_world()
        if not w:return
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['n']+=1
        value=a.get_locomotion_root_window()
        if value:
            roots,times=value;p=roots[1].translation;d=roots[2].translation-p
            s['rows'].append(dict(t=t,p=[p.x,p.y,p.z],delta=[d.x,d.y,d.z],factors=list(c.call_method('GetLocomotionRootWindowSmoothing',(a,))),speed=a.get_locomotion_state()[0].length()))
        if s['n']>=240:finish('complete')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
