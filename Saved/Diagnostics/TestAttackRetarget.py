"""Bounded owned PIE: active Trigger edits must preserve phase, pose and root."""
import unreal,time,json,pathlib,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackRetargetPIE.json'
s=dict(start=time.monotonic(),world=None,last=-1.,phase='setup',rows=[],seen_armed=False,seen_hit=False)
def lib(name):return unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.'+name))
control=lib('ProphecyAttackControlLibrary');defense=lib('ProphecyNNDefenseLibrary');root=lib('ProphecyRootPhysicsLibrary')
def call(obj,name,*args):return obj.call_method(name,tuple(args))
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
    out.write_text(json.dumps(dict(error=error,rows=s['rows']),indent=2))
    print('ATTACK_RETARGET',error or 'PASS')
def state(a):
    x=a.get_nn_attack_state()
    return None if not x else (str(x[0]),bool(x[1]),bool(x[2]),bool(x[3]),int(x[4]))
def check(a,target,family=None,half=None):
    before=state(a);assert before
    name=family or before[0];mode=before[1] if half is None else half
    root_before=a.get_root_low_point()
    pose_before=a.read_nn_future_world_pose()[2]
    assert a.trigger_nn_attack(name,target,mode,s['victim'])
    after=state(a)
    assert after[0].lower()==name.lower() and after[1]==mode,(before,after)
    assert after[2:]==before[2:],('Phase reset',before,after)
    assert (a.get_root_low_point()-root_before).length()<1.e-6,'Root handoff during retarget'
    pose_after=a.read_nn_future_world_pose()[2]
    assert max((x.translation-y.translation).length() for x,y in zip(pose_before,pose_after))<1.e-6,'Pose changed during retarget'
    assert (a.get_nn_attack_target()[0]-target).length()<1.e-6,'Target not updated'
    assert a.get_nn_attack_victim()==s['victim']
    return before,after
def tick(_):
    try:
        assert time.monotonic()-s['start']<100,'Timeout'
        w=ed.get_game_world()
        if s['world'] and w!=s['world']:finish('Owned Play ended/replaced');return
        if not w:return
        s['world']=w
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        if s['phase']=='setup':
            if t<1.:return
            actors=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
            assert len(actors)>=2
            for a in actors:
                a.set_actor_tick_enabled(False)
                call(defense,'StopNNDefense',a);a.stop_nn_attack();a.stop_locomotion_input()
                assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            a,d=actors[:2];s.update(actor=a,victim=d,phase='settle',time=t)
            return
        a=s['actor']
        if s['phase']=='settle':
            if t-s['time']<.3:return
            facing=a.get_locomotion_state()[1]
            target=a.get_authored_body_world_target('head')[2].translation+facing*85
            assert a.trigger_nn_attack('slashRU',target,False,s['victim'])
            s.update(phase='running',target=target,time=t)
            # Even static initialization must apply only to a fresh start.
            assert call(control,'SetAttackInitializationMode',a,unreal.ProphecyAttackInitializationMode.STATIC)
        if s['phase']=='running':
            before=state(a)
            if not before:
                assert s['seen_armed'] and s['seen_hit'],('Attack ended without phases',s)
                assert a.trigger_nn_attack('hookL',s['target'],False,s['victim'])
                fresh=state(a);assert fresh and not fresh[2] and not fresh[3] and fresh[4]==1,fresh
                assert a.stop_nn_attack()
                assert a.trigger_nn_attack('slashRU',s['target'],True,s['victim'])
                check(a,s['target']+unreal.Vector(1,0,0),'hookR',True)
                check(a,s['target'],'hookR',False)
                check(a,s['target'],'hookR',True)
                a.stop_nn_attack()
                s['rows'].append(dict(stage='natural_end_fresh_stop_and_half_switches',passed=True))
                finish();return
            assert t-s['time']<12.,'Retriggers prevented natural completion'
            check(a,s['target'])
            unchanged=state(a)
            assert not a.trigger_nn_attack('not_an_attack',s['target'],False,s['victim'])
            assert state(a)==unchanged,'Invalid family mutated attack'
            assert not a.trigger_nn_attack('kickR',s['target'],True,s['victim'])
            assert state(a)==unchanged,'Invalid half kick mutated attack'
            if before[2] and not s['seen_armed']:
                s['seen_armed']=True
                first,after=check(a,s['target']+unreal.Vector(1,0,0),'hookL')
                check(a,s['target'],'slashRU')
                s['rows'].append(dict(stage='armed_family_change',before=first,after=after))
            if before[3] and not s['seen_hit']:
                s['seen_hit']=True
                first,after=check(a,s['target'],'pike')
                check(a,s['target'],'slashRU')
                s['rows'].append(dict(stage='hit_family_change',before=first,after=after))
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
