import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
families=['slashL','slashR','slashLD','slashRD','slashLU','slashRU','pike','jabL','jabR','hookL','hookR','overL','overR','headbutt']
s=dict(start=time.monotonic(),a=None,index=0,rows=[],next=0.)
def done(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/IndependentHalfGhost/lifecycle.json').write_text(json.dumps(dict(error=error,rows=s['rows']),indent=2))
    if ed.get_game_world():level.editor_request_end_play()
    print('INDEPENDENT_HALF_LIFECYCLE',error or 'passed')
def tick(_):
    try:
        assert time.monotonic()-s['start']<90,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t<.6:return
        if not s['a']:
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
                a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
                a.set_actor_tick_enabled(False);a.stop_nn_attack()
            s['a']=unreal.GameplayStatics.get_player_pawn(w,0)
        a=s['a']
        if t<s['next']:return
        if s['index']==len(families):done();return
        family=families[s['index']];a.stop_nn_attack()
        names,pose,_,_=a.read_nn_future_world_pose();p=pose[[str(n) for n in names].index('pelvis')].translation
        target=p+unreal.Vector(-30,90,30)
        assert a.trigger_nn_attack(family,target,True)
        before=a.get_nn_attack_state();assert before[-1]==1
        for half in [True,False,True]:
            assert a.set_nn_half_attack_enabled(half)
            state=a.get_nn_attack_state();assert state[1]==half and state[2:]==before[2:]
        target+=unreal.Vector(140,200,0)
        assert a.trigger_nn_attack(family,target,True)
        assert a.get_nn_attack_state()==before
        assert all((v-target).length()<.001 for v in a.get_nn_attack_target())
        for invalid in ['kickL','kickR','not_an_attack']:
            assert not a.trigger_nn_attack(invalid,target,True)
            assert a.get_nn_attack_state()==before
        s['rows'].append(dict(family=family,initial_frame=1,mode_switches=True,retrigger=True,invalid_preserved=True))
        s['index']+=1;s['next']=t+.2
    except Exception:done(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
