import builtins,json,pathlib,sys,time,traceback,unreal
clock_setup=sys.argv[1] if len(sys.argv)>1 else 'project'
key='_prophecy_mode_sequence'
previous=getattr(builtins,key,None)
if previous and previous.get('handle'): raise RuntimeError('A mode-sequence sampler is active')
state={'handle':None,'rows':[],'events':[],'done':False,'error':None,'first_t':None,'last_t':None,
       'path':str(pathlib.Path(unreal.Paths.project_saved_dir()).resolve()/'Diagnostics/CameraRelativeHitch'/('mode-sequence-'+time.strftime('%H%M%S')+'.json'))}
setattr(builtins,key,state)
phases=[unreal.ProphecyAgentSimulationMode.PHYSICAL,unreal.ProphecyAgentSimulationMode.KINEMATIC,
        unreal.ProphecyAgentSimulationMode.HALF_SIM,unreal.ProphecyAgentSimulationMode.PHYSICAL]
def vec(v): return [float(v.x),float(v.y),float(v.z)]
def finish(reason):
    if state['handle']: unreal.unregister_slate_post_tick_callback(state['handle'])
    state['handle']=None; state['done']=True; state['reason']=reason
    pathlib.Path(state['path']).write_text(json.dumps({k:v for k,v in state.items() if k not in ('handle','finish')},separators=(',',':')))
    print('MODE_SEQUENCE_DONE',reason,len(state['rows']),state['path'])
state['finish']=finish
def tick(slate_dt):
    start=time.perf_counter()
    try:
        world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        if not world:
            if state['first_t'] is not None: finish('PIE ended')
            return
        now=float(unreal.GameplayStatics.get_time_seconds(world))
        if now==state['last_t'] or now<2: return
        agent=unreal.GameplayStatics.get_player_pawn(world,0)
        if not isinstance(agent,unreal.ProphecyAgent): return
        if state['first_t'] is None:
            state['first_t']=now
            state['dirty_content']=[str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
            state['dirty_maps']=[str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
            if clock_setup=='runtime':
                unreal.FixedFrameRateLibrary.set_fixed_frame_rate_runtime(60.0)
            elif clock_setup!='project': raise ValueError(clock_setup)
            state['events'].append({'t':now,'action':'clock setup','source':clock_setup})
        elapsed=now-state['first_t']; phase=min(3,int(elapsed//30))
        if phase!=state.get('phase',0):
            before={'mode':str(agent.get_simulation_mode()),'jolt':agent.is_jolt_physical_animation_enabled()}
            before_mesh=agent.get_pose_reference_mesh()
            before_pose={str(n):vec(before_mesh.get_socket_location(n)) for n in ('pelvis','head','hand_l','hand_r','foot_l','foot_r')}
            result=agent.set_simulation_mode(phases[phase])
            state['events'].append({'t':now,'action':'mode change','requested':str(phases[phase]),'success':result,
                'before':before,'after':{'mode':str(agent.get_simulation_mode()),'jolt':agent.is_jolt_physical_animation_enabled()},
                'before_pose':before_pose,'after_pose':{n:vec(agent.get_pose_reference_mesh().get_socket_location(n)) for n in before_pose}})
            state['phase']=phase
        mesh=agent.get_pose_reference_mesh(); pose=agent.read_nn_future_world_pose()
        if not mesh or not pose: return
        names,future,targets,alpha=pose
        points={str(n):{'target':vec(t.translation),'visible':vec(mesh.get_socket_location(n))}
                for n,t in zip(names,targets) if str(n) in ('pelvis','head','hand_l','hand_r','foot_l','foot_r','spine_03')}
        body=agent.get_physical_body_state('pelvis')
        camera=unreal.GameplayStatics.get_player_camera_manager(world,0)
        row={'t':now,'wall':start,'dt':float(unreal.GameplayStatics.get_world_delta_seconds(world)),
            'phase':phase,'mode':str(agent.get_simulation_mode()),'jolt':agent.is_jolt_physical_animation_enabled(),
            'alpha':float(alpha),'root':vec(agent.get_actor_location()),'camera':vec(camera.get_camera_location()),
            'bones':points,'body_p':vec(body[0].translation) if body else None,'body_v':vec(body[1]) if body else None}
        row['sample_ms']=(time.perf_counter()-start)*1000; state['rows'].append(row); state['last_t']=now
        if elapsed>=120: finish('Duration complete'); return
        injection=phase*2+(1 if elapsed%30>=20 else 0)
        if elapsed%30>=10 and injection not in state.setdefault('injected',[]):
            delay=.15 if injection%2 else .06
            state['events'].append({'t':now,'action':'delay','seconds':delay})
            state['injected'].append(injection); time.sleep(delay)
    except Exception:
        state['error']=traceback.format_exc(); finish('Capture error')
state['handle']=unreal.register_slate_post_tick_callback(tick)
if not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('MODE_SEQUENCE_STARTED',state['path'])
