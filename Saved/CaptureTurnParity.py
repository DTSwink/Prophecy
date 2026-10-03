import unreal,json,time,traceback,builtins
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
out=Path(unreal.Paths.project_saved_dir())/'Diagnostics/TurnParity'
out.mkdir(parents=True,exist_ok=True)
trace=Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/nn_inputs.jsonl'
s=dict(rows=[],metadata=[],last=-1,agents=[],offset=trace.stat().st_size if trace.exists() else 0,wall=time.monotonic())
builtins._turn_parity=s
bones=['pelvis','spine_01','spine_05','neck_01','head','thigh_l','thigh_r','calf_l','calf_r','foot_l','foot_r','ball_l','ball_r']
def vec(p):return [p.x,p.y,p.z]
def tf(t):return vec(t.translation)+[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    w=ed.get_game_world()
    if w:unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 0')
    (out/'current.json').write_text(json.dumps(dict(reason=reason,metadata=s['metadata'],rows=s['rows']),separators=(',',':')))
    if trace.exists():
        with trace.open('rb') as f:f.seek(s['offset']);(out/'current_inputs.jsonl').write_bytes(f.read())
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('TURN_CAPTURE',reason,len(s['rows']))
def tick(_):
    try:
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        if not s['agents']:
            s['agents']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
            if not s['agents']:return
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 1500')
            for a in s['agents']:
                a.set_foot_pinning_debug_enabled(True)
                m=dict(actor=a.get_name(),label=a.get_actor_label(),properties={})
                for prop in ['simulation_mode','physical_drive_mode','b_upper_nn_has_sword','upper_nn_gaze_yaw_normalized','upper_nn_gaze_pitch_normalized',
                    'body_magnetization_settings','physical_feedback_tolerances','world_magnetization_linear_strength_scale','world_magnetization_angular_strength_scale']:
                    try:m['properties'][prop]=str(a.get_editor_property(prop))
                    except:pass
                for c in ['ProphecyWalkPinningLibrary','ProphecyHandInertiaLibrary','ProphecyPelvisInertiaLibrary']:
                    try:
                        lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.'+c))
                        if c=='ProphecyWalkPinningLibrary':m[c]=str(lib.call_method('GetWalkPinningTolerance',(a,)))
                        elif c=='ProphecyPelvisInertiaLibrary':m[c]=str(lib.call_method('GetPelvisInertia',(a,)))
                    except Exception as e:m[c]=str(e)
                s['metadata'].append(m)
        for a in s['agents']:
            p=a.read_nn_future_world_pose()
            if not p:continue
            names,future,shown,alpha=p
            lookup={str(n):i for i,n in enumerate(names)}
            inp=a.get_editor_property('locomotion_input')
            mesh=a.get_pose_reference_mesh()
            row=dict(t=t,actor=a.get_name(),mode=str(a.get_simulation_mode()),jolt=a.is_jolt_physical_animation_enabled(),
                interp=str(a.get_nn_interpolation_mode()),attack=str(a.get_nn_attack_state()),
                move=vec(inp.world_move_input),facing=vec(inp.facing_world_direction),run=inp.run,
                root=tf(a.get_actor_transform()),alpha=alpha,bones={},
                gaze=[a.get_editor_property('upper_nn_gaze_yaw_normalized'),a.get_editor_property('upper_nn_gaze_pitch_normalized')])
            try:row['tick']=a.get_editor_property('tick debug')
            except:pass
            pin=a.get_locomotion_foot_pinning()
            if pin:row['pin']=dict(raw=[pin.raw_network_output.x,pin.raw_network_output.y],effective=[pin.effective_pinning.x,pin.effective_pinning.y],walk=pin.walk_policy)
            for bone in bones:
                if bone not in lookup:continue
                i=lookup[bone]
                row['bones'][bone]=dict(target=tf(future[i]),shown=tf(shown[i]),actual=tf(mesh.get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_WORLD)))
            s['rows'].append(row)
        if t>=40:finish('complete')
        elif time.monotonic()-s['wall']>180:finish('wall limit')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('Capturing unchanged current scene for 40 simulation seconds')
