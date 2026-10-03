import unreal,json,time,traceback,math
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
api=unreal.ProphecyNNDefenseLibrary
s={'phase':'init','started':time.monotonic(),'last':None,'tick':0,'rows':[],'episode':0,'seen':set()}
out=Path(unreal.Paths.project_saved_dir())/'Diagnostics'/('SpecialRecoveryLive-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    level.editor_request_end_play()
    out.write_text(json.dumps({'error':error,'seen':list(s['seen']),'rows':s['rows']},indent=2))
    print('SPECIAL_RECOVERY_LIVE_DONE',str(out),error)
def tick(dt):
    try:
        assert time.monotonic()-s['started']<100,'Timed out'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['tick']+=1
        if s['phase']=='init':
            if s['tick']<45:return
            agents=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            agents=sorted(agents,key=lambda a:not a.is_player_controlled())
            assert len(agents)>=2
            for a in agents:
                a.stop_nn_attack();api.stop_nn_defense(a);a.stop_locomotion_input()
                a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
                a.set_actor_tick_enabled(False)
                lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyUpperBodyInertiaLibrary'))
                assert lib.call_method('SetAttackUpperBodyInertia',args=(a,True,.25,0.,.5,1.))
            s.update(agents=agents,a=agents[1],d=agents[0],phase='settle',end=s['tick']+20)
        for p in s['agents']:p.apply_nn_pose_kinematically(dt)
        a,d=s['a'],s['d']
        if s['phase']=='settle' and s['tick']>=s['end']:
            a.stop_nn_attack();api.stop_nn_defense(d)
            target=d.get_authored_body_world_target('head')[1].translation
            assert a.trigger_nn_attack('overL',target,False,d)
            mode=['parry','dodge','parry','dodge'][s['episode']]
            result=api.start_nn_parry(d,a,3.) if mode=='parry' else api.start_nn_dodge(d,a,3.)
            assert result is not None,mode+' rejected'
            s.update(phase='special',mode=mode,active_seen=False,start=s['tick'])
        state=str(api.get_agent_state(d))
        if s['phase']=='special':
            if ('PARRYING' in state or 'DODGING' in state):
                s['active_seen']=True;s['seen'].add(s['mode'])
                if s['episode']>=2 and s['tick']-s['start']>10:api.stop_nn_defense(d)
            elif s['active_seen']:
                s.update(phase='return',end=s['tick']+70)
            elif s['tick']-s['start']>150:raise AssertionError('Defense never became active')
        pose=d.read_nn_future_world_pose()
        if pose:
            names,future,presented,alpha=pose
            head=presented[[str(n) for n in names].index('head')]
            values=[head.translation.x,head.translation.y,head.translation.z]
            assert all(math.isfinite(x) for x in values),'Non-finite head'
            s['rows'].append({'tick':s['tick'],'episode':s['episode'],'phase':s['phase'],'state':state,'head':values,'weights':list(d.get_locomotion_checkpoint_weights())})
        if s['phase']=='return' and s['tick']>=s['end']:
            assert 'LOCOMOTION' in str(api.get_agent_state(d))
            s['episode']+=1
            if s['episode']==4:finish();return
            s.update(phase='settle',end=s['tick']+15)
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
print('SPECIAL_RECOVERY_LIVE_STARTED',str(out))
