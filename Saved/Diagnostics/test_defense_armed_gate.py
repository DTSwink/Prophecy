"""Short disposable-PIE check: no defense ownership/inference before learned Armed."""
import unreal, pathlib, json, time, traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
api=unreal.ProphecyNNDefenseLibrary
assert not ed.get_game_world()
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/DefenseArmedGate'
folder.mkdir(parents=True,exist_ok=True)
s=dict(start=time.monotonic(),phase='setup',rows=[],cases=[],last=None)

def point(actor): return actor.get_authored_body_world_target('head')[1].translation
def finish(result,error=''):
    unreal.unregister_slate_post_tick_callback(s['callback'])
    if ed.get_game_world(): level.editor_request_end_play()
    (folder/'PIE.json').write_text(json.dumps(dict(result=result,error=error,rows=s['rows'],cases=s['cases']),indent=2))
    print('DEFENSE_ARMED_GATE',result,error)

def request(mode):
    a,d=s['a'],s['d']
    value=api.start_nn_dodge(d,a,3.) if mode=='dodge' else api.start_nn_parry(d,a,unreal.ProphecyParryBlocker.RIGHT_ARM,3.)
    assert value is not None,('request failed',mode)
    status=api.get_nn_defense_status(d)
    assert status and not status.active and status.completed_steps==0,('took ownership before Armed',mode)

def launch(mode):
    a,d=s['a'],s['d']
    api.stop_nn_defense(d);a.stop_nn_attack();d.stop_nn_attack();d.stop_locomotion_input()
    assert a.trigger_nn_attack('headbutt',point(d),False)
    assert not a.get_nn_attack_state()[2]
    request(mode)
    if mode=='dodge':
        # A queued response must not prevent the defender's own attack.
        assert d.trigger_nn_attack('hookL',point(a),False)
        assert d.get_nn_attack_state()
    else:
        d.set_locomotion_input(unreal.Vector(0,.35,0),False,unreal.Vector(0,1,0),1.,1.)
    s.update(phase=mode,pre=0,armed_frame=None,activation_frame=None,root=d.get_root_low_point(),max_move=0.,launched=time.monotonic(),last=None)

def tick(dt):
    try:
        assert time.monotonic()-s['start']<75,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if s['phase']=='setup':
            actors=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
            players=[a for a in actors if a.is_player_controlled() and a.has_valid_agent_handle()]
            if not players:return
            a=players[0];d=a.get_editor_property('CombatDemoOpponent')
            if not d or not d.has_valid_agent_handle():return
            a.set_editor_property('CombatDemoAttackEveryFrames',100000)
            if t<.3:return
            assert a.get_simulation_mode()==d.get_simulation_mode()==unreal.ProphecyAgentSimulationMode.KINEMATIC
            s.update(a=a,d=d)
            api.stop_nn_defense(d);a.stop_nn_attack();d.stop_nn_attack()
            # Explicit cancellation and same-family replacement both remove waits.
            assert a.trigger_nn_attack('headbutt',point(d),False)
            request('dodge');assert api.stop_nn_defense(d)
            v=api.get_nn_defense_status(d);assert not v or not v.active
            request('parry');assert a.trigger_nn_attack('headbutt',point(d),False)
            v=api.get_nn_defense_status(d);assert not v or not v.active
            assert not api.stop_nn_defense(d),'same-family replacement left a pending request'
            s['cases'].append(dict(case='explicit cancellation and same-family replacement',passed=True))
            launch('dodge');return
        a,d=s['a'],s['d'];attack=a.get_nn_attack_state();status=api.get_nn_defense_status(d)
        assert attack and status,(s['phase'],attack,status)
        frame=attack[4];armed=attack[2]
        key=(s['phase'],frame,status.completed_steps,status.active)
        if key==s['last']:return
        s['last']=key
        displacement=(d.get_root_low_point()-s['root']).length()
        s['max_move']=max(s['max_move'],displacement)
        s['rows'].append(dict(mode=s['phase'],attacker_frame=frame,armed=armed,defense_active=status.active,defense_steps=status.completed_steps,defender_attack=bool(d.get_nn_attack_state()),root_displacement_cm=displacement))
        if not armed:
            s['pre']+=1
            assert not status.active and status.completed_steps==0,'defense ran before Armed'
            if s['phase']=='dodge':assert d.get_nn_attack_state(),'queued defense stopped own attack'
        else:
            if s['armed_frame'] is None:s['armed_frame']=frame
            if status.active and s['activation_frame'] is None:s['activation_frame']=frame
            # Close scene contacts can legitimately end defense on its first step.
            if status.completed_steps>=1:
                assert s['pre']>=2,'insufficient pre-Armed observation'
                assert s['activation_frame']==s['armed_frame'],('late activation',s['activation_frame'],s['armed_frame'])
                assert not d.get_nn_attack_state(),'own attack not released for defense'
                if s['phase']=='parry':assert s['max_move']>.1,'locomotion did not advance'
                s['cases'].append(dict(mode=s['phase'],pre_armed_samples=s['pre'],armed_frame=s['armed_frame'],activation_frame=s['activation_frame'],completed_steps=status.completed_steps,root_displacement_cm=s['max_move']))
                if s['phase']=='dodge':launch('parry')
                else:finish('passed')
        assert time.monotonic()-s['launched']<20,('attack did not reach Armed/defense',s['phase'])
    except Exception:finish('failed',traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
