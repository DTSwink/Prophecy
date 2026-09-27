"""Owned PIE only: current authored attack setup, block before entry, release at tick170."""
import unreal,pathlib,json,time,traceback,sys
force_half=len(sys.argv)>1 and sys.argv[1]=='half'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackControls';out.mkdir(exist_ok=True)
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyGhostAttackLibrary'))
s=dict(start=time.monotonic(),last=None,frame=0,rows=[])
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    (out/('armed-block-half.json' if force_half else 'armed-block.json')).write_text(json.dumps(dict(error=error,rows=s['rows']),indent=2))
    print('ARMED_BLOCK_CAPTURE_DONE',error or 'complete',len(s['rows']))
    if ed.get_game_world():level.editor_request_end_play()
def tick(_):
    try:
        assert time.monotonic()-s['start']<60,'Timed out'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['frame']+=1
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        f=s['frame']
        if f==95:assert api.call_method('SetAttackArmedBlocked',args=(a,True))
        if f==121 and force_half:assert a.set_nn_half_attack_enabled(True)
        state=a.get_nn_attack_state()
        if f>=95:
            s['rows'].append(dict(frame=f,state=[str(state[0]),*state[1:]] if state else None))
        if f==170:assert api.call_method('SetAttackArmedBlocked',args=(a,False))
        if f>=230:
            held=[r for r in s['rows'] if 120<=r['frame']<=170 and r['state']]
            released=[r for r in s['rows'] if r['frame']>170 and r['state']]
            assert held and held[-1]['frame']==170,'No continuously held attack through release'
            assert not any(r['state'][2] or r['state'][3] for r in held),'Armed/Hit escaped block'
            if force_half:assert all(r['state'][1] for r in held if r['frame']>121),'Half wind-up not retained'
            assert any(r['state'][2] for r in released),'Did not arm after release'
            assert any(r['state'][3] for r in released),'Did not hit after release'
            finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
