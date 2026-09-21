import unreal, builtins, pathlib, json, time, traceback, sys
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
duration=float(sys.argv[2]) if len(sys.argv)>2 else 90.0
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world(), 'Start outside PIE'
if mode=='cold_start': unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),'Prophecy.Jolt.Diagnostic.WristWarmStart 0')
if mode.startswith('projected'): unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),'Prophecy.Jolt.Diagnostic.WristProject 1')
if 'trace' in mode: unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),'Prophecy.Jolt.Diagnostic.WristTrace 1')
if mode.startswith('speculative'): unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),'Prophecy.Jolt.Diagnostic.WristSpeculative 1')
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/WristSnap'
state=dict(handle=None, actors=[], joints={}, metadata=[], rows=[], last=None, start=None, wall=time.perf_counter(), next_report=15)
builtins._wrist_snap_capture=state
def q(v): return [v.x,v.y,v.z,v.w]
def v(a): return [a.x,a.y,a.z]
def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    (out/(mode+'.json')).write_text(json.dumps(dict(reason=reason, metadata=state['metadata'],rows=state['rows']),separators=(',',':')))
    print('WRIST_SNAP_CAPTURE_DONE',mode,reason,len(state['rows']))
    if mode=='cold_start': unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),'Prophecy.Jolt.Diagnostic.WristWarmStart 1')
    if mode.startswith('projected'): unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),'Prophecy.Jolt.Diagnostic.WristProject 0')
    if 'trace' in mode: unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),'Prophecy.Jolt.Diagnostic.WristTrace 0')
    if mode.startswith('speculative'): unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),'Prophecy.Jolt.Diagnostic.WristSpeculative 0')
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(dt):
    try:
        world=sub.get_game_world()
        if not world: return
        t=unreal.GameplayStatics.get_time_seconds(world)
        if t==state['last']: return
        state['last']=t
        if not state['actors']:
            if t<2: return
            state['actors']=list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent))
            assert state['actors']
            for a in state['actors']:
                if mode.startswith('chaos'): a.disable_jolt_physical_animation()
                if mode.startswith('no_self'): a.set_jolt_self_collision_enabled(False)
                mesh=a.get_pose_reference_mesh()
                matches=[c for c in mesh.get_constraints(True) if set(str(n) for n in unreal.ConstraintInstanceBlueprintLibrary.get_attached_body_names(c)[1:])=={'hand_l','lowerarm_l'}]
                assert len(matches)==1
                state['joints'][a.get_name()]=matches[0]
                state['metadata'].append(dict(actor=a.get_name(),jolt=a.is_jolt_physical_animation_enabled(),
                    magnetization={b:str(a.get_body_magnetization_settings(b)) for b in ('hand_l','lowerarm_l','upperarm_l')},
                    feedback={b:str(a.get_physical_feedback_tolerance(b)) for b in ('hand_l','lowerarm_l','upperarm_l')}))
            state['start']=t
        for a in state['actors']:
            pose=a.read_nn_future_world_pose()
            if not pose: continue
            names,future,presented,alpha=pose
            lookup={str(n):i for i,n in enumerate(names)}
            mesh=a.get_pose_reference_mesh()
            row=dict(t=t,wall=time.perf_counter()-state['wall'],actor=a.get_name(),alpha=alpha,jolt=a.is_jolt_physical_animation_enabled(),bones={})
            for bone in ('hand_l','lowerarm_l','upperarm_l','hand_r','lowerarm_r'):
                body=a.get_physical_body_state(bone)
                if not body or bone not in lookup: continue
                tr,lin,ang,sim=body
                row['bones'][bone]=dict(q=q(tr.rotation),p=v(tr.translation),w=v(ang),target=q(presented[lookup[bone]].rotation),future=q(future[lookup[bone]].rotation),visible=q(mesh.get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_WORLD).rotation))
            row['limits']=str(unreal.ConstraintInstanceBlueprintLibrary.get_angular_limits(state['joints'][a.get_name()])[1:])
            state['rows'].append(row)
        elapsed=t-state['start']
        if elapsed>=state['next_report']:
            print('WRIST_SNAP_PROGRESS',mode,round(elapsed,1),len(state['rows']))
            state['next_report']+=15
        if elapsed>=duration: finish('Complete')
        elif time.perf_counter()-state['wall']>360: finish('Wall timeout')
    except Exception: finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('WRIST_SNAP_CAPTURE_START',mode,duration)
