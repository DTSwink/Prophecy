"""Temporary PIE experiment. No assets or defaults are saved. End PIE restores it."""
import builtins, json, pathlib, sys, time, traceback
import unreal

mode=sys.argv[1] if len(sys.argv)>1 else 'physical'
feedback=sys.argv[2] if len(sys.argv)>2 else 'authored'
clock=sys.argv[3] if len(sys.argv)>3 else 'variable'
root=pathlib.Path(unreal.Paths.project_saved_dir()).resolve()/'Diagnostics/CameraRelativeHitch'
scope={'__name__':'__mode_experiment__'}
source=(root/'capture.py').read_text()
source=source.replace(" or not agent.is_jolt_physical_animation_enabled()", "")
source=source.replace("mesh=comps['PhysicalMesh']", "mesh=agent.get_pose_reference_mesh()")
source=source.replace("'sampling':'Slate post-tick", "'mode':str(agent.get_simulation_mode()),'jolt':agent.is_jolt_physical_animation_enabled(),'sampling':'Slate post-tick")
source=source.replace("row['sample_ms']=", """row['bones']={str(n):{'target':vec(p.translation),'target_q':[float(p.rotation.x),float(p.rotation.y),float(p.rotation.z),float(p.rotation.w)],'visible':vec(objects['mesh'].get_socket_location(n))} for n,p in zip(names,presented) if str(n) in ('pelvis','head','hand_l','hand_r','foot_l','foot_r','spine_03')}
            row['mode']=str(agent.get_simulation_mode())
            row['sample_ms']=""")
exec(compile(source,str(root/'capture.py'),'exec'),scope)
state=scope['state']; objects=scope['objects']; original_tick=scope['tick']
unreal.unregister_slate_post_tick_callback(state['handle']); state['handle']=None
state['path']=str(root/(mode+'-'+feedback+'-'+clock+'-'+time.strftime('%H%M%S')+'.json'))
state['experiment']={'mode':mode,'feedback':feedback,'clock':clock,'injections':[],'setup':None}
original_finish=scope['finish']
def finish(reason):
    original_finish(reason)
    if clock=='fixed': unreal.FixedFrameRateLibrary.disable_fixed_frame_rate_runtime()
scope['finish']=finish

def tick(dt):
    try:
        world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        if not world: return original_tick(dt)
        now=float(unreal.GameplayStatics.get_time_seconds(world))
        if state['experiment']['setup'] is None:
            if now<2: return
            agent=unreal.GameplayStatics.get_player_pawn(world,0)
            if not isinstance(agent,unreal.ProphecyAgent): return
            if mode=='half':
                if agent.is_jolt_physical_animation_enabled(): agent.disable_jolt_physical_animation()
                result=agent.set_simulation_mode(unreal.ProphecyAgentSimulationMode.HALF_SIM)
                if not result: raise RuntimeError('HalfSim transition failed')
            elif mode!='physical': raise ValueError(mode)
            before=scope['settings'](agent)
            if feedback=='none': agent.set_all_physical_feedback_tolerances(10000,360)
            elif feedback!='authored': raise ValueError(feedback)
            if clock=='fixed': unreal.FixedFrameRateLibrary.set_fixed_frame_rate_runtime(60.0)
            elif clock!='variable': raise ValueError(clock)
            state['experiment']['setup']={'t':now,'before':before,'after':scope['settings'](agent),
                'mode':str(agent.get_simulation_mode()),'jolt':agent.is_jolt_physical_animation_enabled()}
        original_tick(dt)
        if state['done']: return
        elapsed=now-state['first_t'] if state['first_t'] is not None else 0
        injections=state['experiment']['injections']
        if elapsed>=25+len(injections)*2 and len(injections)<16:
            delay=(.035,.060,.100,.150)[len(injections)%4]
            before=time.perf_counter(); time.sleep(delay)
            injections.append({'after_t':now,'requested_seconds':delay,'actual_seconds':time.perf_counter()-before})
    except Exception:
        state['error']=traceback.format_exc(); scope['finish']('Mode experiment error')

state['handle']=unreal.register_slate_post_tick_callback(tick)
print('MODE_CAPTURE_STARTED',state['path'])
