import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyGhostAttackLibrary'))
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/HalfPelvisMount';out.mkdir(exist_ok=True)
trace=out.parent/'SlashContacts/live_steps.jsonl'
s=dict(start=time.monotonic(),actors=[],rows=[],events=[],case=-1,bytes=trace.stat().st_size if trace.exists() else 0)
families=['hookL','slashR','headbutt','pike']
def tr(t):return dict(p=[t.translation.x,t.translation.y,t.translation.z],q=[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w])
def done(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    w=ed.get_game_world()
    if w:
        unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceFrames 0')
        unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceAgent -1')
    if trace.exists():
        with trace.open('rb') as f:f.seek(s['bytes']);(out/'trace.jsonl').write_bytes(f.read())
    (out/'live.json').write_text(json.dumps(dict(error=error,rows=s['rows'],events=s['events']),indent=2))
    if w:level.editor_request_end_play()
    print('HALF_PELVIS_MOUNT_DONE',error or 'passed',len(s['rows']))
def tick(_):
    try:
        assert time.monotonic()-s['start']<150,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t<.6:return
        if not s['actors']:
            s['actors']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
            for a in s['actors']:
                a.stop_nn_attack();a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC);a.set_actor_tick_enabled(False)
            s['a']=unreal.GameplayStatics.get_player_pawn(w,0)
            assert s['a'] in s['actors']
            a=s['a']
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceAgent '+str(a.get_agent_handle().index))
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceFrames 500')
            assert not api.call_method('VisualizeGhostAttack',args=(a,False,unreal.Vector(150,0,0),0.,1.))
        a=s['a'];case=int((t-1)/2.) if t>=1 else -1
        if 0<=case<len(families) and case!=s['case']:
            a.stop_nn_attack();s['case']=case
            names,pose,_,_=a.read_nn_future_world_pose();pelvis=pose[[str(n) for n in names].index('pelvis')].translation
            a.set_locomotion_input(unreal.Vector(1,0,0),False,unreal.Vector(0,1 if case%2 else -1,0),1.,1.)
            assert a.trigger_nn_attack(families[case],pelvis+unreal.Vector(-30,70,30),True)
            before=a.get_nn_attack_state();assert a.set_nn_half_attack_enabled(True);assert before==a.get_nn_attack_state()
            assert api.call_method('VisualizeGhostAttack',args=(a,True,unreal.Vector(150,0,0),0.,1.))
            s['events'].append(dict(case=case,family=families[case],start=t,debug_draw=True,idempotent=True))
        state=a.get_nn_attack_state()
        if state:
            names,pose,_,_=a.read_nn_future_world_pose()
            s['rows'].append(dict(t=t,family=str(state[0]).lower(),frame=state[-1],half=state[1],pose={str(n):tr(p) for n,p in zip(names,pose)}))
            api.call_method('VisualizeGhostAttack',args=(a,True,unreal.Vector(150,0,0),0.,1.))
        if t>9.2:
            a.stop_nn_attack();assert not api.call_method('VisualizeGhostAttack',args=(a,True,unreal.Vector(150,0,0),0.,1.))
            done()
    except Exception:done(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
