import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
api=unreal.ProphecyNNDefenseLibrary
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LiveParryLifecycle';folder.mkdir(parents=True,exist_ok=True)
s={'phase':'start','start':time.monotonic(),'rows':[]}
def status(a):
    v=api.get_nn_defense_status(a);assert v
    return v
def note(label):
    values=[status(a) for a in s['defenders']]
    s['rows'].append(dict(phase=label,steps=[v.completed_steps for v in values],active=[v.active for v in values],attacker_frames=[v.attacker_frame for v in values]))
def finish(result,error=''):
    unreal.unregister_slate_post_tick_callback(s['callback'])
    if ed.get_game_world():level.editor_request_end_play()
    (folder/'PIE.json').write_text(json.dumps(dict(result=result,error=error,rows=s['rows']),indent=2)+'\n')
    print('LIVE_PARRY_LIFECYCLE',result,error)
def tick(dt):
    try:
        assert time.monotonic()-s['start']<90,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if s['phase']=='start':
            if t<1:return
            actors=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
            assert len(actors)>=3
            a,d0,d1=actors[:3]
            for p in (a,d0,d1):
                p.set_actor_tick_enabled(False);p.stop_nn_attack();p.stop_locomotion_input();p.stop_nn_animation_layer(0)
                assert p.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            if not a.get_held_sword():assert a.equip_sword(False)
            if not d0.get_held_sword():assert d0.equip_sword(False)
            d1.hide_sword();assert not d1.get_held_sword()
            target=d0.get_authored_body_world_target('spine_03')[1].translation
            assert a.trigger_nn_attack('slashRU',target,False)
            assert api.start_nn_parry(d0,a,unreal.ProphecyParryBlocker.BLADE,3) is not None
            assert api.start_nn_parry(d1,a,unreal.ProphecyParryBlocker.LEFT_ARM,3) is not None
            s.update(attacker=a,defenders=[d0,d1],phase='both',time=t);note('two started')
        for p in [s['attacker'],*s['defenders']]:p.apply_nn_pose_kinematically(dt)
        d0,d1=s['defenders'];a=s['attacker']
        v0,v1=status(d0),status(d1)
        if s['phase']=='both' and min(v0.completed_steps,v1.completed_steps)>=3:
            assert v0.active and v1.active
            assert v0.attacker_frame==v1.attacker_frame==a.get_nn_attack_state()[4]
            assert api.stop_nn_defense(d0);s.update(phase='one',stopped=v0.completed_steps,other=v1.completed_steps);note('one stopped')
        elif s['phase']=='one' and v1.completed_steps>=s['other']+3:
            assert not v0.active and v0.completed_steps==s['stopped'] and v1.active
            assert api.start_nn_parry(d0,a,unreal.ProphecyParryBlocker.RIGHT_ARM,3) is not None
            assert status(d0).completed_steps==0;s.update(phase='restart');note('first restarted')
        elif s['phase']=='restart' and v0.completed_steps>=3:
            assert v0.active and v1.active and v0.attacker_frame==v1.attacker_frame==a.get_nn_attack_state()[4]
            note('two after restart');assert a.stop_nn_attack();s.update(phase='ended',time=t)
        elif s['phase']=='ended' and t-s['time']>.15:
            assert not v0.active and not v1.active;note('opponent stopped');finish('passed')
    except Exception:finish('failed',traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
