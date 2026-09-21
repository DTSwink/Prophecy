import builtins, json, pathlib, time, traceback
import unreal

key='_prophecy_camera_relative_hitch'
prior=getattr(builtins,key,None)
if prior and prior.get('handle'): raise RuntimeError('A camera-relative capture is already active')
old=getattr(builtins,'_prophecy_pelvis_backward_capture',None)
if old and old.get('handle'): raise RuntimeError('Previous pelvis sampler still active')
root=pathlib.Path(unreal.Paths.project_saved_dir()).resolve()/'Diagnostics/CameraRelativeHitch'
root.mkdir(parents=True,exist_ok=True)
state={'handle':None,'rows':[],'metadata':{},'first_t':None,'last_t':None,'started_wall':time.perf_counter(),
       'path':str(root/('capture-'+time.strftime('%H%M%S')+'.json')),'done':False,'error':None}
setattr(builtins,key,state)
objects={}

def vec(v): return [float(v.x),float(v.y),float(v.z)]
def rot(v): return [float(v.pitch),float(v.yaw),float(v.roll)]
def settings(agent):
    return {'feedback':str(agent.get_physical_feedback_tolerance('pelvis')),
        'self_collision_hand_head':str(agent.get_jolt_body_pair_self_collision_enabled('hand_l','head')),
        'input':str(agent.get_editor_property('locomotion_input')),'sword':str(agent.get_held_sword())}
def finish(reason):
    if state['handle']: unreal.unregister_slate_post_tick_callback(state['handle'])
    state['handle']=None
    state['done']=True
    state['reason']=reason
    if objects.get('agent'): state['final_settings']=settings(objects['agent'])
    pathlib.Path(state['path']).write_text(json.dumps({k:v for k,v in state.items() if k not in ('handle','finish')},separators=(',',':')))
    print('CAMERA_RELATIVE_CAPTURE_DONE',len(state['rows']),reason,state['path'])
state['finish']=finish

def tick(slate_dt):
    started=time.perf_counter()
    try:
        world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        if not world:
            if objects: finish('PIE ended')
            elif started-state['started_wall']>30: finish('No PIE world')
            return
        now=float(unreal.GameplayStatics.get_time_seconds(world))
        if now==state['last_t']: return
        if not objects:
            agent=unreal.GameplayStatics.get_player_pawn(world,0)
            if not isinstance(agent,unreal.ProphecyAgent) or not agent.is_jolt_physical_animation_enabled(): return
            comps={c.get_name():c for c in agent.get_components_by_class(unreal.ActorComponent)}
            objects.update(agent=agent,mesh=comps['PhysicalMesh'],camera=unreal.GameplayStatics.get_player_camera_manager(world,0),
                           controller=unreal.GameplayStatics.get_player_controller(world,0),comps=comps)
            state['metadata']={'actor':agent.get_path_name(),'initial_settings':settings(agent),
                'sampling':'Slate post-tick, world-time deduplicated, cached camera manager POV and projection; no setters, sleeps or forced pose evaluation',
                'components':list(comps)}
            physics=unreal.get_default_object(unreal.PhysicsSettings)
            state['metadata']['physics']={n:physics.get_editor_property(n) for n in ('substepping','max_substep_delta_time','max_substeps')}
            state['first_t']=now
            spring=comps.get('SpringArm')
            if spring:
                state['metadata']['spring_arm']={}
                for name in ('enable_camera_lag','enable_camera_rotation_lag','do_collision_test','target_arm_length','camera_lag_speed'):
                    try: state['metadata']['spring_arm'][name]=str(spring.get_editor_property(name))
                    except Exception: pass
        agent=objects['agent']; camera=objects['camera']; controller=objects['controller']
        pose=agent.read_nn_future_world_pose(); body=agent.get_physical_body_state('pelvis'); motion=agent.get_locomotion_state()
        if pose and body and motion:
            names,future,presented,alpha=pose
            pelvis=next(i for i,n in enumerate(names) if str(n)=='pelvis')
            root_position=agent.get_actor_location()
            body_position=body[0].translation
            points={'root':root_position,'target':presented[pelvis].translation,'future':future[pelvis].translation,
                    'pelvis':body_position,'visible':objects['mesh'].get_socket_location('pelvis')}
            projected={}
            for name in ('root','target','pelvis'):
                p=unreal.GameplayStatics.project_world_to_screen(controller,points[name],False)
                projected[name]=[float(p.x),float(p.y)] if p else None
            row={'t':now,'wall':started,'dt':float(unreal.GameplayStatics.get_world_delta_seconds(world)),
                 'slate_dt':float(slate_dt),'alpha':float(alpha),'mover_v':vec(motion[0]),'body_v':vec(body[1]),
                 'camera':vec(camera.get_camera_location()),'camera_rotation':rot(camera.get_camera_rotation()),
                 'fov':float(camera.get_fov_angle()),'screen':projected,**{k:vec(v) for k,v in points.items()}}
            row['sample_ms']=(time.perf_counter()-started)*1000
            state['rows'].append(row)
        state['last_t']=now
        if now-state['first_t']>=65: finish('Duration complete')
    except Exception:
        state['error']=traceback.format_exc(); finish('Capture error')

state['handle']=unreal.register_slate_post_tick_callback(tick)
if not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if '/Game/testNN.' not in world.get_path_name(): finish('Unexpected editor map'); raise RuntimeError('Expected testNN')
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('CAMERA_RELATIVE_CAPTURE_STARTED',state['path'])
