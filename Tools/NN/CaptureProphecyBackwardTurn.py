"""Read-only gameplay observation: run user's current Blueprint unchanged."""
import builtins,json,pathlib,traceback,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/BackwardTurn'
out.mkdir(parents=True,exist_ok=True)
trace=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/nn_inputs.jsonl'
s=dict(rows=[],last=-1,started=False,offset=trace.stat().st_size if trace.exists() else 0)
builtins._backward_turn_capture=s
def v(p):return [p.x,p.y,p.z]
def tf(t):return v(t.translation)+[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]
def done(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    w=ed.get_game_world()
    if w:unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 0')
    (out/'scene.json').write_text(json.dumps(dict(reason=reason,rows=s['rows'])))
    if trace.exists():
        with trace.open('rb') as f:
            f.seek(s['offset']);(out/'inputs.jsonl').write_bytes(f.read())
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('BACKWARD_TURN_CAPTURE',reason,len(s['rows']))
def tick(_):
    try:
        w=ed.get_game_world()
        if not w:return
        now=unreal.GameplayStatics.get_time_seconds(w)
        if now==s['last']:return
        s['last']=now
        if not s['started']:
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 140')
            s['started']=True
        for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
            p=a.read_nn_future_world_pose()
            if not p:continue
            names,future,shown,alpha=p
            inp=a.get_editor_property('locomotion_input')
            mesh=a.get_pose_reference_mesh()
            r=dict(t=now,actor=a.get_name(),handle=a.get_agent_handle().index,tick=a.get_editor_property('tick debug'),
                mode=str(a.get_simulation_mode()),interp=str(a.get_nn_interpolation_mode()),attack=str(a.get_nn_attack_state()),
                move=v(inp.world_move_input),run=inp.run,facing=v(inp.facing_world_direction),
                root=tf(a.get_actor_transform()),alpha=alpha,
                future={str(n):tf(t) for n,t in zip(names,future)},shown={str(n):tf(t) for n,t in zip(names,shown)},
                mesh={n:tf(mesh.get_socket_transform(n,unreal.RelativeTransformSpace.RTS_WORLD)) for n in ['pelvis','calf_l','calf_r','foot_l','foot_r','ball_l','ball_r']})
            s['rows'].append(r)
        if now>=4:done('complete')
    except Exception:done(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
