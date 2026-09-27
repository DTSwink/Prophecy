"""Owned early PIE lifecycle checks, before the scene's authored attack at120."""
import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyGhostAttackLibrary'))
magic=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
setters=['SetRootMagicVelocity','SetRootMagicAngVelocity','SetRootMagicVelocity2','SetRootMagicAngVelocity2']
getters=['GetRootMagicVelocity','GetRootMagicAngVelocity','GetRootMagicVelocity2','GetRootMagicAngVelocity2']
s=dict(start=time.monotonic(),last=None,frame=0,rows=[])
def seed(a):
    for name in setters:assert magic.call_method(name,args=(a,unreal.Vector(30,40,50),False))
def values(a):
    return [[v.x,v.y,v.z] for v in [magic.call_method(n,args=(a,)) for n in getters]]
def cleared(a):assert all(all(abs(x)<1.e-6 for x in v) for v in values(a)),values(a)
def count(a):return api.call_method('GetTicksSinceLastAttack',args=(a,))
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    p=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/AttackControls/entry-magic-ticks.json')
    p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(dict(error=error,rows=s['rows']),indent=2))
    print('ATTACK_ENTRY_CAPTURE_DONE',error or 'complete',len(s['rows']))
    if ed.get_game_world():level.editor_request_end_play()
def tick(_):
    try:
        assert time.monotonic()-s['start']<60,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['frame']+=1;f=s['frame']
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        if f==40:
            assert not a.get_nn_attack_state()
            assert count(a)==0
            assert api.call_method('SetAttackArmedBlocked',args=(a,True))
            s['target']=a.read_nn_future_world_pose()[1][0].translation+unreal.Vector(100,0,0)
            seed(a);assert a.trigger_nn_attack('slashL',s['target'],False,None);cleared(a);assert count(a)==0
        if f==45:assert a.set_nn_half_attack_enabled(True);assert count(a)==0
        if f==48:
            seed(a);before=values(a)
            assert not a.trigger_nn_attack('invalid_attack_for_test',s['target'],False,None)
            assert count(a)==3 and values(a)==before
        if f==50:
            assert count(a)==5
            seed(a);before=values(a)
            assert a.trigger_nn_attack('slashL',s['target'],True,None)
            assert count(a)==5 and values(a)==before
        if f==55:
            seed(a);assert a.set_nn_half_attack_enabled(False);cleared(a);assert count(a)==0
        if f==60:assert a.set_nn_half_attack_enabled(True);assert count(a)==0
        if f==65:assert count(a)==5;assert a.stop_nn_attack();assert count(a)==5
        if f==70:
            seed(a);before=values(a)
            assert a.trigger_nn_attack('slashL',s['target'],True,None)
            assert count(a)==10 and values(a)==before
        if f==75:assert a.stop_nn_attack();assert count(a)==15
        if f==80:
            seed(a);assert a.trigger_nn_attack('slashL',s['target'],False,None);cleared(a);assert count(a)==0
        if f==82:assert a.stop_nn_attack();assert count(a)==0
        if f>=40:
            n=count(a)
            if 40<=f<45 or 55<=f<60 or 80<=f<82:assert n==0,(f,n)
            s['rows'].append(dict(frame=f,ticks=n,state=str(a.get_nn_attack_state())))
        if f==87:assert count(a)==5;finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
