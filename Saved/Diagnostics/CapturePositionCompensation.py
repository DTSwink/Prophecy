import unreal,pathlib,json,time,traceback,sys
tag=sys.argv[1];position=int(sys.argv[2]) if len(sys.argv)>2 else -1;distributed=int(sys.argv[3]) if len(sys.argv)>3 else 0
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PositionCompensation';out.mkdir(exist_ok=True)
trace=out.parent/'SlashContacts/live_steps.jsonl'
s=dict(start=time.monotonic(),last=None,frame=0,rows=[],bytes=trace.stat().st_size if trace.exists() else 0)
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyGhostAttackLibrary'))
def tr(t):return [t.translation.x,t.translation.y,t.translation.z,t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    w=ed.get_game_world()
    if w:
        unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceFrames 0')
        unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceAgent -1')
    if trace.exists():
        with trace.open('rb') as f:f.seek(s['bytes']);(out/(tag+'-trace.jsonl')).write_bytes(f.read())
    (out/(tag+'.json')).write_text(json.dumps(dict(error=error,rows=s['rows']),separators=(',',':')))
    print('POSITION_COMPENSATION_DONE',tag,error or 'complete',len(s['rows']));s['rows'].clear()
    if w:level.editor_request_end_play()
def tick(_):
    try:
        assert time.monotonic()-s['start']<75,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['frame']+=1
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        if s['frame']==30:
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceAgent '+str(a.get_agent_handle().index))
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceFrames 150')
        if s['frame']>=95:
            state=a.get_nn_attack_state();pose=a.read_nn_future_world_pose()
            names,future,presented,alpha=pose
            targets=a.get_nn_attack_target() if state else None
            s['rows'].append(dict(frame=s['frame'],t=t,state=list(state) if state else None,targets=[[v.x,v.y,v.z] for v in targets] if targets else None,names=[str(n) for n in names],future=[tr(p) for p in future],presented=[tr(p) for p in presented]))
            if s['rows'][-1]['state']:s['rows'][-1]['state'][0]=str(state[0])
        # Only a paired diagnostic override in this owned Play session. The
        # user's Blueprint continues to trigger attacks and mode switches.
        if position>=0 and s['frame']>=95:
            assert api.call_method('EnableSpine01CompensationHalfAttack',args=(a,True,bool(distributed),bool(position)))
        if s['frame']>=220:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
