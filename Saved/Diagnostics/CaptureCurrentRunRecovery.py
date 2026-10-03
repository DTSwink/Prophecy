import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
s=dict(start=time.monotonic(),last=None,frame=0,rows=[])
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/CurrentRunRecovery.json').write_text(json.dumps(dict(error=error,rows=s['rows']),indent=2))
    print('RUN_RECOVERY_CAPTURE_DONE',error or 'complete',len(s['rows']))
    if ed.get_game_world():level.editor_request_end_play()
def tick(_):
    try:
        assert time.monotonic()-s['start']<60,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['frame']+=1
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        if s['frame']>=105:
            state=a.get_nn_attack_state();weights=a.get_locomotion_checkpoint_weights()
            s['rows'].append(dict(frame=s['frame'],state=[str(state[0]),*state[1:]] if state else None,weights=list(weights) if weights else None,target=str(a.get_locomotion_target())))
        if s['frame']>=230:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
