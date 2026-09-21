"""Real scene NN attack + parry; changes only disposable PIE actors."""
import unreal, pathlib, json, time, traceback, math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LiveDodgeClosePair'
folder.mkdir(parents=True,exist_ok=True)
s={'phase':'start','start':time.monotonic(),'rows':[],'last_steps':-1}
api=unreal.ProphecyNNDefenseLibrary
def vec(v):return [v.x,v.y,v.z]
def point(a,bone):
    x=a.get_authored_body_world_target(bone)
    assert x,('missing target',bone)
    return x[1].translation
def finish(result,error=''):
    unreal.unregister_slate_post_tick_callback(s['callback'])
    if ed.get_game_world():level.editor_request_end_play()
    report={k:v for k,v in s.items() if k in ('rows','agents','initial_distance_cm','max_hand_motion_cm','max_attacker_hand_motion_cm','final_steps','attack_distance_cm')}
    report.update(result=result,error=error,scope='Two actual testNN PIE actors, live attack and dodge NN, kinematic presentation; no prerecorded poses.')
    (folder/'PIE.json').write_text(json.dumps(report,indent=2)+'\n')
    print('LIVE_DODGE_PAIR',result,error)
def tick(dt):
    try:
        assert time.monotonic()-s['start']<120,'PIE test timeout'
        world=ed.get_game_world()
        if not world:return
        t=unreal.GameplayStatics.get_time_seconds(world)
        if s['phase']=='start':
            if t<1:return
            actors=[a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
            assert len(actors)>=2,'Need two live managed scene agents'
            for a in actors:
                a.set_actor_tick_enabled(False)  # Suppress this fixture's unrelated Blueprint debug loop.
                a.stop_nn_attack();a.stop_locomotion_input()
                assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            d,a=min(((d,a) for d in actors for a in actors if a!=d),key=lambda p:(point(p[0],'pelvis')-point(p[1],'pelvis')).length())
            if not d.get_held_sword():assert d.equip_sword(False)
            if not a.get_held_sword():assert a.equip_sword(False)
            s.update(defender=d,attacker=a,actors=actors,agents=[a.get_name(),d.get_name()],
                     initial_distance_cm=(point(d,'pelvis')-point(a,'pelvis')).length(),phase='approach',time=t)
        for a in s.get('actors',[]):a.apply_nn_pose_kinematically(dt)
        if s['phase']=='approach':
            a,d=s['attacker'],s['defender']
            delta=point(d,'pelvis')-point(a,'pelvis');delta.z=0
            if delta.length()>140:
                direction=delta.normal()
                a.set_locomotion_input(direction,False,direction,1.,1.)
                d.set_locomotion_input(unreal.Vector(),False,-direction,0.,1.)
            else:
                a.stop_locomotion_input();d.stop_locomotion_input();s.update(phase='settle',time=t)
        if s['phase']=='settle' and t-s['time']>.3:
            a,d=s['attacker'],s['defender']
            assert a.trigger_nn_attack('slashRU',point(d,'spine_03'),False),'Attack failed'
            assert api.start_nn_dodge(d,a,2.0) is not None,'Dodge start failed'
            status=api.get_nn_defense_status(d);assert status and status.active
            s.update(phase='active',time=t,attack_distance_cm=(point(d,'pelvis')-point(a,'pelvis')).length(),initial_hand=point(d,'hand_r'),initial_attack_hand=point(a,'hand_r'),
                     max_hand_motion_cm=0.,max_attacker_hand_motion_cm=0.)
        elif s['phase']=='active':
            d,a=s['defender'],s['attacker'];status=api.get_nn_defense_status(d);assert status
            attack=a.get_nn_attack_state()
            if status.active and status.completed_steps:
                assert attack and status.attacker_frame==attack[4],('stale attacker frame',status.attacker_frame,attack)
            pose=d.read_nn_future_world_pose();assert pose
            assert all(math.isfinite(v) for tr in pose[1] for v in vec(tr.translation)),'Nonfinite defense pose'
            s['max_hand_motion_cm']=max(s['max_hand_motion_cm'],(point(d,'hand_r')-s['initial_hand']).length())
            s['max_attacker_hand_motion_cm']=max(s['max_attacker_hand_motion_cm'],(point(a,'hand_r')-s['initial_attack_hand']).length())
            if status.completed_steps!=s['last_steps']:
                s['rows'].append(dict(time=t,steps=status.completed_steps,attacker_frame=status.attacker_frame,
                    actual_attacker_frame=attack[4] if attack else None,active=status.active,blocked=status.blocked,
                    harmful=status.harmful_contact,hand=vec(point(d,'hand_r')),pelvis=vec(point(d,'pelvis')),
                    contact=str(status.contact_collider),contact_seconds=status.contact_time_seconds))
                s['last_steps']=status.completed_steps
            if (not status.active) or t-s['time']>1.8:
                assert status.completed_steps>=1,('too few defense steps',status.completed_steps)
                assert s['max_hand_motion_cm']>.05 and s['max_attacker_hand_motion_cm']>.05,'No actual pose motion'
                api.stop_nn_defense(d);s.update(phase='stopped',time=t,final_steps=status.completed_steps)
        elif s['phase']=='stopped' and t-s['time']>.15:
            status=api.get_nn_defense_status(s['defender'])
            assert status and not status.active and status.completed_steps==s['final_steps'],'Stopped defense still inferred'
            finish('passed')
    except Exception:finish('failed',traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
