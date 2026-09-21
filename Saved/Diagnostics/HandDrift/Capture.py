import unreal, builtins, pathlib, json, time, traceback, sys
mode = sys.argv[1] if len(sys.argv)>1 else 'jolt'
sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if sub.get_game_world(): raise RuntimeError('Start capture outside PIE')
unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),'Prophecy.Jolt.Diagnostic.COMTarget '+str({'jolt_com':1,'jolt_twist':2}.get(mode,0)))
conditioning=unreal.SystemLibrary.get_console_variable_int_value('p.Chaos.Solver.InertiaConditioning.Enabled')
if mode=='chaos_no_condition': unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),'p.Chaos.Solver.InertiaConditioning.Enabled 0')
out = pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/HandDrift'
out.mkdir(parents=True, exist_ok=True)
state = dict(rows=[], agents=[], metadata=[], handle=None, start=None, last=None, wall=time.perf_counter())
builtins._hand_drift = state
def vec(v): return [v.x,v.y,v.z]
def quat(q): return [q.x,q.y,q.z,q.w]
def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    state['handle']=None
    result=dict(mode=mode, reason=reason, metadata=state['metadata'], rows=state['rows'])
    (out/(mode+'.json')).write_text(json.dumps(result,separators=(',',':')))
    print('HAND_CAPTURE_DONE',mode,reason,len(state['rows']))
    if mode=='chaos_no_condition': unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),'p.Chaos.Solver.InertiaConditioning.Enabled '+str(conditioning))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(dt):
    try:
        world=sub.get_game_world()
        if not world:
            if state['start'] is not None: finish('PIE ended')
            return
        t=unreal.GameplayStatics.get_time_seconds(world)
        if t==state['last']: return
        state['last']=t
        if not state['agents']:
            if t<2: return
            agents=list(unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent))
            if not agents: return
            for a in agents:
                if mode.startswith('chaos'): a.disable_jolt_physical_animation()
                elif not a.is_jolt_physical_animation_enabled():
                    if not a.enable_jolt_physical_animation(): raise RuntimeError('Jolt enable failed')
                if mode=='jolt_no_self':
                    print('HAND_NO_SELF',a.get_name(),a.set_jolt_self_collision_enabled(False))
                if mode=='jolt_no_limits':
                    print('HAND_NO_LIMITS',a.get_name(),a.set_use_authored_angular_limits(False))
                state['metadata'].append(dict(actor=a.get_name(), mode=str(a.get_simulation_mode()),
                    world_linear=a.get_editor_property('world_magnetization_linear_strength_scale'),
                    world_angular=a.get_editor_property('world_magnetization_angular_strength_scale'),
                    settings={b:str(a.get_body_magnetization_settings(b)) for b in ('hand_l','hand_r','lowerarm_l','lowerarm_r','upperarm_l','upperarm_r')},
                    mesh=str(a.get_pose_reference_mesh().get_collision_profile_name())))
            state['agents']=agents;state['start']=t
            return
        for a in state['agents']:
            row=dict(t=t,actor=a.get_name(),jolt=a.is_jolt_physical_animation_enabled(),root=vec(a.get_actor_location()),bones={})
            pose=a.read_nn_future_world_pose()
            if not pose: continue
            names,future,presented,alpha=pose
            lookup={str(n):i for i,n in enumerate(names)}
            for b in ('pelvis','spine_05','upperarm_l','upperarm_r','lowerarm_l','lowerarm_r','hand_l','hand_r'):
                body=a.get_physical_body_state(b)
                if not body or b not in lookup: continue
                tr,v,w,sim=body;target=presented[lookup[b]]
                row['bones'][b]=dict(p=vec(tr.translation),q=quat(tr.rotation),v=vec(v),w=vec(w),target=vec(target.translation),tq=quat(target.rotation),sim=bool(sim))
            state['rows'].append(row)
        if t-state['start']>=25: finish('Complete')
        elif time.perf_counter()-state['wall']>150: finish('Wall timeout')
    except Exception: finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('HAND_CAPTURE_START',mode)
