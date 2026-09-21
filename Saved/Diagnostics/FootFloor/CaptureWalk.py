import builtins, unreal, pathlib, json, time, traceback, sys

backend = sys.argv[1] if len(sys.argv) > 1 else 'jolt'
editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
    raise RuntimeError('Begin each comparison from a fresh PIE session for the same authored start.')
for name,value in (
    ('BounceThresholdCm', 200 if backend == 'jolt_bounce200' else -1),
    ('SpeculativeDistanceCm', 0.1 if backend == 'jolt_spec01' else -1),
    ('PenetrationSlopCm', 0.1 if backend == 'jolt_slop01' else -1)):
    unreal.SystemLibrary.execute_console_command(editor_world, 'Prophecy.Jolt.Diagnostic.' + name + ' ' + str(value))
key = '_prophecy_foot_floor_capture'
old = getattr(builtins, key, None)
if old and old.get('handle'): raise RuntimeError('Foot capture already active')
state = dict(handle=None, rows=[], agents=[], metadata=[], last_t=None, start_t=None,
             started=time.perf_counter(), backend=backend, done=False, error=None)
setattr(builtins, key, state)
out = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/FootFloor'
state['path'] = str(out / (backend + '-' + time.strftime('%H%M%S') + '.json'))
def vec(v): return [float(v.x), float(v.y), float(v.z)]
def finish(reason):
    if state['handle']: unreal.unregister_slate_post_tick_callback(state['handle'])
    state['handle'] = None
    state['done'] = True
    state['reason'] = reason
    pathlib.Path(state['path']).write_text(json.dumps({k:v for k,v in state.items() if k not in ('agents','handle','finish')}, separators=(',',':')))
    print('FOOT_CAPTURE_DONE', reason, len(state['rows']), state['path'])
state['finish'] = finish
def tick(dt):
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        if not world:
            if state['agents']: finish('PIE ended')
            elif time.perf_counter() - state['started'] > 90: finish('No PIE world')
            return
        now = float(unreal.GameplayStatics.get_time_seconds(world))
        if now == state['last_t']: return
        state['last_t'] = now
        if not state['agents']:
            if now < 1: return
            agents = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent))
            if not agents or any(a.get_simulation_mode() != unreal.ProphecyAgentSimulationMode.PHYSICAL for a in agents): return
            for a in agents:
                if backend in ('jolt_zero_friction','jolt_zero_restitution'):
                    a.disable_jolt_physical_animation()
                    pm=unreal.PhysicalMaterial()
                    pm.set_editor_property('friction',0.0 if backend == 'jolt_zero_friction' else 0.7)
                    pm.set_editor_property('static_friction',0.0)
                    pm.set_editor_property('restitution',0.3 if backend == 'jolt_zero_friction' else 0.0)
                    a.get_pose_reference_mesh().set_phys_material_override(pm)
                    if backend == 'jolt_zero_restitution':
                        floor=next(x for x in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor) if x.get_actor_label()=='Floor')
                        floor.get_component_by_class(unreal.StaticMeshComponent).set_phys_material_override(pm)
                if backend == 'chaos': a.disable_jolt_physical_animation()
                elif not a.enable_jolt_physical_animation(): raise RuntimeError('Could not enable Jolt')
                if backend == 'jolt_ignore_floor':
                    floor=next(x for x in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor) if x.get_actor_label()=='Floor')
                    channel=floor.get_component_by_class(unreal.StaticMeshComponent).get_collision_object_type()
                    a.get_pose_reference_mesh().set_collision_response_to_channel(channel, unreal.CollisionResponseType.ECR_IGNORE)
                state['metadata'].append(dict(actor=a.get_name(), initial=vec(a.get_actor_location()), mode=str(a.get_simulation_mode())))
            if backend == 'jolt_zero_restitution':
                for actor in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor):
                    for scene in actor.get_components_by_class(unreal.ProphecyJoltSceneCollisionComponent):
                        scene.disable_scene_collision()
                        result=scene.enable_scene_collision()
                        print('FOOT_FLOOR_REIMPORT',result)
                        if not scene.is_scene_collision_enabled(): raise RuntimeError('Static collision reimport failed: '+str(result))
            state['agents'] = agents
            state['start_t'] = now
            return
        for a in state['agents']:
            pose = a.read_nn_future_world_pose()
            if not pose: continue
            names, future, presented, alpha = pose
            lookup = {str(n):i for i,n in enumerate(names)}
            row = dict(t=now, actor=a.get_name(), jolt=a.is_jolt_physical_animation_enabled(),
                       root=vec(a.get_actor_location()), dt=float(unreal.GameplayStatics.get_world_delta_seconds(world)), feet={})
            for bone in ('foot_l','ball_l','foot_r','ball_r'):
                body = a.get_physical_body_state(bone)
                if not body or bone not in lookup: continue
                transform, linear, angular, simulating = body
                target = presented[lookup[bone]]
                row['feet'][bone] = dict(p=vec(transform.translation), v=vec(linear), w=vec(angular),
                    q=[transform.rotation.x,transform.rotation.y,transform.rotation.z,transform.rotation.w],
                    target=vec(target.translation), sim=bool(simulating))
            state['rows'].append(row)
        if now - state['start_t'] >= 25: finish('Complete')
        elif time.perf_counter() - state['started'] > 150: finish('Wall timeout')
    except Exception:
        state['error'] = traceback.format_exc()
        finish('Error')
state['handle'] = unreal.register_slate_post_tick_callback(tick)
if not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('FOOT_CAPTURE_STARTED', state['path'])
