import builtins,json,pathlib,time,traceback,unreal
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not e.get_game_world()
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PolicyBlendRuntime.json'
s=dict(start=time.monotonic(),last=-1,events=[],samples=[],n=0)
builtins._policy_blend_test=s
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    out.write_text(json.dumps(dict(reason=reason,events=s['events'],samples=s['samples'])))
    if e.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('POLICY_BLEND_RUNTIME',reason)
def tick(_):
    try:
        if time.monotonic()-s['start']>100:finish('timeout');return
        w=e.get_game_world()
        if not w:return
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['n']+=1;n=s['n']
        if n==10:
            assert tuple(a.get_locomotion_policy_blend_times())==(0.,0.)
            assert a.set_locomotion_policy_blend_times(.3,.6)
            assert not a.set_locomotion_policy_blend_times(-1.,.8)
            wr,rw=a.get_locomotion_policy_blend_times();assert abs(wr-.3)<1e-6 and abs(rw-.6)<1e-6
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            # Keep the user's saved Tick graph untouched; this transient fixture owns intent.
            a.set_actor_tick_enabled(False)
            a.set_locomotion_input(unreal.Vector(1,0,0),False,unreal.Vector(1,0,0))
        if n in (90,160,240,250,330,420):
            run=n in (90,240,330)
            a.set_locomotion_running(run)
            s['events'].append(dict(frame=n,run=run,time=t))
        if n==450:
            assert a.set_locomotion_policy_blend_times(0,0)
            a.set_locomotion_running(True)
        if n>=11:
            row=dict(frame=n,time=t)
            for bone in ['pelvis','thigh_r','calf_r','foot_r','hand_r']:
                v=a.get_authored_body_world_target(bone)
                assert v is not None, bone
                x=v[1];p=x.translation;q=x.rotation
                row[bone]=[p.x,p.y,p.z,q.x,q.y,q.z,q.w]
                assert all(__import__('math').isfinite(z) for z in row[bone])
            s['samples'].append(row)
        if n>=480:finish('complete')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
