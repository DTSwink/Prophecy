"""PIE-only clamp bounds and previous-input renderer capture. No asset writes."""
import builtins, json, math, pathlib, time, traceback, unreal
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
directory=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts'
contract=json.loads((pathlib.Path(unreal.Paths.project_content_dir())/'locomotion/NN/prophecy_lower_body_runtime.json').read_text())
lengths={name:math.sqrt(sum(v*v for v in offset))*100 for name,offset in zip(contract['body_names'],contract['local_offsets_m'])}
upper=json.loads((pathlib.Path(unreal.Paths.project_content_dir())/'locomotion/NN/prophecy_upper_body_runtime.json').read_text())
state=dict(actor=None,last=-1,rows=[],phase=-1,wall=time.perf_counter())
builtins._input_debug_clamps=state
def values(p):return [p.x,p.y,p.z]
def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['callback'])
    world=editor.get_game_world()
    if world:unreal.SystemLibrary.execute_console_command(world,'Prophecy.NNInputTraceFrames 0')
    (directory/'InputDebugClamps.json').write_text(json.dumps(dict(reason=reason,rows=state['rows'])),encoding='utf-8')
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('INPUT_DEBUG_CLAMPS',reason)
def tick(_):
    try:
        world=editor.get_game_world()
        if not world:return
        now=unreal.GameplayStatics.get_time_seconds(world)
        if now==state['last']:return
        state['last']=now
        if state['actor'] is None:
            actor=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent) if a.get_agent_handle().index==0)
            actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            actor.set_actor_tick_enabled(False)
            actor.stop_nn_attack()
            actor.set_locomotion_input(unreal.Vector(0,1,0),False,unreal.Vector(0,1,0),1,1)
            mesh=actor.set_show_nn_previous_pose_debug_mesh(True,False)
            material=actor.get_pose_reference_mesh().get_material(0)
            mesh.set_material(0,material)
            assert mesh.get_material(0)==material
            state['actor']=actor
            unreal.SystemLibrary.execute_console_command(world,'Prophecy.NNInputTraceFrames 120')
        actor=state['actor']
        actor.stop_nn_attack()
        phase=0 if now<1 else 1
        if phase!=state['phase']:
            for part in ['foot','calf','hand']:assert getattr(actor,'set_locomotion_'+part+'_clamp')(True,float(phase))
            state['phase']=phase
        pose=actor.read_nn_future_world_pose()
        roots=actor.get_locomotion_root_window()
        if not pose or not roots:return
        names,future,shown,alpha=pose
        index={str(n):i for i,n in enumerate(names)}
        mesh=actor.get_editor_property('nn_previous_pose_debug_mesh')
        debug={name:values(mesh.get_socket_transform(name,unreal.RelativeTransformSpace.RTS_COMPONENT).translation)
            for name in ['pelvis','hand_l','hand_r','foot_l','foot_r']}
        if now>0.2 and abs(now-1)>0.1:
            for side_index,side in enumerate(['l','r']):
                def distance(a,b):return math.dist(values(future[index[a]].translation),values(future[index[b]].translation))
                assert distance('lowerarm_'+side,'hand_'+side)<=upper['arm_limb_lengths_m'][side_index][1]*100+phase+0.001
                assert abs(distance('calf_'+side,'foot_'+side)-lengths['foot_'+side])<=phase+0.001
                assert distance('thigh_'+side,'foot_'+side)<=lengths['calf_'+side]+lengths['foot_'+side]+phase+0.001
        state['rows'].append(dict(t=now,actor=actor.get_name(),phase=phase,debug=debug,
            roots=[values(r.translation)+[r.rotation.x,r.rotation.y,r.rotation.z,r.rotation.w] for r in roots[0]],times=list(roots[1])))
        if now>=2.2:finish('Complete')
        elif time.perf_counter()-state['wall']>90:finish('Timeout')
    except Exception:finish(traceback.format_exc())
state['callback']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
