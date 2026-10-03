import builtins, json, math, pathlib, time, traceback, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play session'
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/GTAttackIdle20260930'
s=dict(last=None,wall=time.monotonic(),rows=[],starts=[],ends=[],prior=None,deadline=None,done=False)
builtins._gt_attack_idle_smoke=s

def finish(reason):
    if s['done']:return
    s['done']=True
    unreal.unregister_slate_post_tick_callback(s['handle'])
    (folder/'KinematicLoopSmoke.json').write_text(json.dumps({k:v for k,v in s.items() if k not in ('wall','handle')},default=str,indent=2))
    (folder/'KinematicLoopSmokeStatus.txt').write_text(reason)
    level.editor_request_end_play()
    print('GT_ATTACK_IDLE_SMOKE_DONE',reason)

def tick(_):
    try:
        if time.monotonic()-s['wall']>100:finish('Timeout');return
        w=ed.get_game_world()
        if not w:return
        now=unreal.GameplayStatics.get_time_seconds(w)
        if now==s['last']:return
        s['last']=now
        a=next((a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.is_player_controlled()),None)
        if not a:return
        frame=int(a.get_editor_property('tick debug'))
        if frame==20:
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
        state=a.get_nn_attack_state()
        failed=a.get_editor_property('Codex GT Failed')
        was=a.get_editor_property('Codex GT Was Attacking')
        deadline=a.get_editor_property('Codex GT Next Time')
        target=a.get_editor_property('Codex GT World Target')
        assert not failed, ('Loop reported error',frame,str(a.get_simulation_mode()),a.is_nn_animation_layer_active(),state)
        if state and not s['prior']:
            s['starts'].append(dict(frame=frame,time=now,state=state,deadline=deadline,target=[target.x,target.y,target.z]))
            assert str(state[0]).lower()=='slashr',state
            assert not state[1], ('Expected full attack on entry',state)
            if len(s['starts'])==1:assert frame==30, ('First attack timing',frame)
            else:assert now+1e-5>=deadline and now-deadline<0.1, ('Cooldown not respected',now,deadline)
        if not state and s['prior']:s['ends'].append(dict(frame=frame,time=now))
        s['prior']=state
        if deadline!=s['deadline'] and deadline>0:
            assert abs(deadline-now-1.0)<0.1, ('Expected one-second cooldown from completion',now,deadline)
        s['deadline']=deadline
        pose=a.read_nn_future_world_pose()
        if pose:
            for t in pose[1]:assert all(math.isfinite(x) for x in [t.translation.x,t.translation.y,t.translation.z,t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w])
        s['rows'].append(dict(frame=frame,time=now,state=state,was=was,deadline=deadline))
        if len(s['starts'])>=3 and len(s['ends'])>=2:finish('Complete')
        elif frame>=480:finish('Insufficient repeats by frame480')
    except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('GT_ATTACK_IDLE_SMOKE_STARTED')
