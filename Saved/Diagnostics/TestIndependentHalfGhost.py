import unreal,json,pathlib,time,traceback,sys
tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/IndependentHalfGhost';out.mkdir(exist_ok=True)
trace=out.parent/'SlashContacts/live_steps.jsonl'
s=dict(start=time.monotonic(),actors=[],rows=[],events=[],case=-1,bytes=trace.stat().st_size if trace.exists() else 0)
families=['hookL','slashR','headbutt','pike']
def xyz(v):return [v.x,v.y,v.z]
def tr(t):return dict(p=xyz(t.translation),q=[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w])
def done(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    w=ed.get_game_world()
    if w:
        unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceFrames 0')
        unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceAgent -1')
    if trace.exists():
        with trace.open('rb') as f:f.seek(s['bytes']);(out/(tag+'-trace.jsonl')).write_bytes(f.read())
    (out/(tag+'.json')).write_text(json.dumps(dict(error=error,rows=s['rows'],events=s['events']),indent=2))
    if w:level.editor_request_end_play()
    print('INDEPENDENT_HALF_DONE',tag,error or 'passed',len(s['rows']))
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
                a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
                a.set_actor_tick_enabled(False);a.stop_nn_attack()
            s['a']=unreal.GameplayStatics.get_player_pawn(w,0)
            a=s['a'];assert a in s['actors']
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceAgent '+str(a.get_agent_handle().index))
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashTraceFrames 800')
            a.set_locomotion_input(unreal.Vector(1,0,0),False,unreal.Vector(0,1,0),1.,1.)
        a=s['a'];case=int((t-1.5)/3.) if t>=1.5 else -1
        if 0<=case<len(families) and case!=s['case']:
            a.stop_nn_attack();s['case']=case;s['changed']=False
            names,pose,_,_=a.read_nn_future_world_pose();pelvis=pose[[str(n) for n in names].index('pelvis')].translation
            target=pelvis+unreal.Vector(-30,90,30);s['target']=target
            a.set_locomotion_input(unreal.Vector(1,0,0),False,unreal.Vector(0,1 if case%2 else -1,0),1.,1.)
            assert a.trigger_nn_attack(families[case],target,True)
            s['events'].append(dict(case=case,family=families[case],start=t,target=xyz(target),pose={str(n):tr(p) for n,p in zip(names,pose)}))
        state=a.get_nn_attack_state()
        if state and s['case']>=0:
            if state[-1]>=5 and not s['changed']:
                s['target']=s['target']+unreal.Vector(70,170,15)
                before=a.get_nn_attack_state()
                assert a.set_nn_attack_target(s['target'])
                assert before==a.get_nn_attack_state(),'Retarget reset attack'
                s['changed']=True
                s['events'].append(dict(case=s['case'],retarget_frame=state[-1],target=xyz(s['target'])))
            targets=a.get_nn_attack_target()
            if tag!='baseline':
                assert all((v-s['target']).length()<.001 for v in targets),str(targets)
            names,pose,_,_=a.read_nn_future_world_pose()
            s['rows'].append(dict(t=t,family=str(state[0]).lower(),frame=state[-1],half=state[1],targets=[xyz(v) for v in targets],pose={str(n):tr(p) for n,p in zip(names,pose)}))
        if t>13.7:done()
    except Exception:done(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
