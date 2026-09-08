"""PIE-only checks for root momentum, mass-weighted error, and half target radius.
Temporarily isolates NPC lane 1 from its Blueprint Tick. No asset saves/screenshots.
"""
import json
import math
import time
import traceback
from pathlib import Path
import unreal

world = unreal.EditorLevelLibrary.get_game_world()
assert world
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
agent = next(a for a in agents if a.get_agent_handle().index == 1)
peer = next(a for a in agents if a != agent)
saved = {'mode': agent.get_simulation_mode(), 'tick': agent.is_actor_tick_enabled(),
         'input': agent.get_locomotion_input(), 'override': agent.get_editor_property('use_blueprint_locomotion_input'),
         'nn': agent.get_editor_property('nn_inference_enabled'),
         'radius': agent.call_method('GetGlobalHalfAttackTargetRadius'),
         'fps': unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')}
hit_test = {'handle': None, 'phase': 0, 'rows': [], 'deadline': time.monotonic()+25}
agent.call_method('StopNNAttack')
agent.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
agent.set_actor_tick_enabled(False)
agent.set_nn_inference_enabled(True)
agent.set_locomotion_input(unreal.Vector(), False, unreal.Vector(), 1, 0)


def xyz(v): return [v.x, v.y, v.z]
def diff(a, b): return [x-y for x, y in zip(a, b)]
def close(a, b, tolerance=1e-5): assert math.dist(a, b) < tolerance, (a, b)


def velocities():
    return [xyz(v) for v in agent.call_method('GetRootVelocity')]


def cancel_velocity():
    linear, angular = agent.call_method('GetRootVelocity')
    assert agent.call_method('AddRootImpulse', args=(-linear, -angular, True))


def finish(error=None):
    if hit_test['handle'] is not None:
        unreal.unregister_slate_post_tick_callback(hit_test['handle'])
        hit_test['handle'] = None
    try:
        agent.call_method('StopNNAttack')
        cancel_velocity()
        agent.call_method('SetGlobalHalfAttackTargetRadius', args=(saved['radius'],))
        i = saved['input']
        agent.set_locomotion_input(i.world_move_input, i.run, i.facing_world_direction, i.speed_scale, i.turn_scale)
        agent.set_editor_property('use_blueprint_locomotion_input', saved['override'])
        agent.set_nn_inference_enabled(saved['nn'])
        agent.set_simulation_mode(saved['mode'])
        agent.set_actor_tick_enabled(saved['tick'])
        unreal.SystemLibrary.execute_console_command(world, f"t.MaxFPS {saved['fps']}")
    except Exception:
        error = (error or '')+'\nCleanup: '+traceback.format_exc()
    out = Path(unreal.Paths.project_saved_dir()).resolve() / 'SlashParity/hit_nodes.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'passed': error is None, 'error': error, 'rows': hit_test['rows']}, indent=2))
    print('Hit nodes:', out, 'error=', error)


def read_pose():
    names, future, presented, alpha = agent.read_nn_future_world_pose()
    return {str(n): t for n, t in zip(names, future)}, {str(n): t for n, t in zip(names, presented)}


def check_mass_error():
    agent.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
    agent.set_actor_tick_enabled(False)
    mesh = agent.get_pose_reference_mesh()
    _, target = read_pose()
    expected_linear = [0.0]*3
    expected_angular = [0.0]*3
    total, count = 0.0, 0
    for name, t in target.items():
        b = agent.get_physical_body_state(name)
        if not b or not b[-1]: continue
        actual = b[0]
        mass = mesh.get_bone_mass(name, True)
        if mass <= 0: continue
        total += mass
        count += 1
        for j, e in enumerate(diff(xyz(actual.translation), xyz(t.translation))):
            expected_linear[j] += mass*e
        # Independent quaternion product actual * inverse(target).
        a, q = actual.rotation, t.rotation
        x = -a.w*q.x+a.x*q.w-a.y*q.z+a.z*q.y
        y = -a.w*q.y+a.x*q.z+a.y*q.w-a.z*q.x
        z = -a.w*q.z-a.x*q.y+a.y*q.x+a.z*q.w
        w = a.w*q.w+a.x*q.x+a.y*q.y+a.z*q.z
        length = math.sqrt(x*x+y*y+z*z+w*w)
        sign = (1 if w >= 0 else -1)/length
        x,y,z,w = x*sign,y*sign,z*sign,w*sign
        sine = math.sqrt(x*x+y*y+z*z)
        factor = 2*math.atan2(sine,w)/sine if sine > 1e-12 else 2
        for j, e in enumerate([x,y,z]): expected_angular[j] += mass*factor*e
    result = agent.call_method('GetMassWeightedPoseError')
    assert result is not None and result[3] == count and count > 10
    close(xyz(result[0]), expected_linear, 1e-4)
    close(xyz(result[1]), expected_angular, 1e-4)
    assert abs(result[2]-total) < 1e-4
    # A 1 cm backward displacement of every body must contribute -totalMass on Y.
    original_location = mesh.get_world_location()
    try:
        mesh.set_world_location(original_location+unreal.Vector(0,-1,0), False, True)
        shifted = agent.call_method('GetMassWeightedPoseError')
        close(diff(xyz(shifted[0]),xyz(result[0])), [0,-total,0], 1e-3)
    finally:
        mesh.set_world_location(original_location, False, True)
    # All bodies were just initialized to the data target. A world-Z rotation
    # therefore has a known, nonzero shortest-arc angular contribution.
    original_rotation = mesh.get_world_rotation()
    try:
        mesh.set_world_rotation(unreal.Rotator(pitch=original_rotation.pitch,
            yaw=original_rotation.yaw+5, roll=original_rotation.roll), False, True)
        rotated = agent.call_method('GetMassWeightedPoseError')
        close(xyz(rotated[1]), [0,0,total*math.radians(5)], 1e-3)
    finally:
        mesh.set_world_rotation(original_rotation, False, True)
    hit_test['rows'].append({'mass_error': {'body_count': count, 'total_mass_kg': total,
        'linear_error': xyz(result[0]), 'angular_error': xyz(result[1]),
        'one_cm_shift_delta': diff(xyz(shifted[0]), xyz(result[0])),
        'five_degree_world_z_error': xyz(rotated[1])}})
    agent.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
    agent.set_actor_tick_enabled(False)
    assert agent.call_method('GetMassWeightedPoseError') is None


def tick(_dt):
    try:
        assert time.monotonic() < hit_test['deadline'], 'Test timeout'
        phase = hit_test['phase']
        if phase in [0,2]:
            fps = 60 if phase==0 else 5
            unreal.SystemLibrary.execute_console_command(world, f't.MaxFPS {fps}')
            cancel_velocity()
            mass, inertia = agent.call_method('GetRootImpulseMassProperties')
            before_root = xyz(agent.get_root_low_point())
            before_rotation = agent.get_actor_rotation().yaw
            before = velocities()
            assert agent.call_method('AddRootImpulse', args=(unreal.Vector(300*mass,-200*mass,999), unreal.Vector(12,34,4*inertia),False))
            after = velocities()
            close(diff(after[0],before[0]),[300,-200,0])
            close(diff(after[1],before[1]),[0,0,4])
            assert agent.call_method('AddRootImpulse',args=(unreal.Vector(20,30,0),unreal.Vector(0,0,-1),True))
            close(diff(velocities()[0],after[0]),[20,30,0])
            close(diff(velocities()[1],after[1]),[0,0,-1])
            close(xyz(agent.get_root_low_point()),before_root,1e-10)
            assert agent.get_actor_rotation().yaw==before_rotation
            hit_test['origin'] = before_root
            hit_test['yaw'] = before_rotation
            hit_test['until'] = unreal.GameplayStatics.get_time_seconds(world)+0.5
            hit_test['rows'].append({'impulse': {'fps':fps,'mass_kg':mass,'inertia_kg_cm2':inertia,'velocity':velocities()}})
            hit_test['phase'] += 1
        elif phase in [1,3]:
            if unreal.GameplayStatics.get_time_seconds(world)<hit_test['until']: return
            movement = math.dist(hit_test['origin'],xyz(agent.get_root_low_point()))
            yaw_movement = abs((agent.get_actor_rotation().yaw-hit_test['yaw']+180)%360-180)
            assert movement>1 and yaw_movement>1, (movement,yaw_movement)
            hit_test['rows'].append({'subsequent_movement_cm':movement,'subsequent_yaw_degrees':yaw_movement})
            hit_test['phase'] += 1
        elif phase==4:
            cancel_velocity()
            unreal.SystemLibrary.execute_console_command(world, 't.MaxFPS 60')
            check_mass_error()
            assert not agent.call_method('SetGlobalHalfAttackTargetRadius',args=(-1.0,))
            assert agent.call_method('SetGlobalHalfAttackTargetRadius',args=(125.0,))
            assert peer.call_method('GetGlobalHalfAttackTargetRadius')==125.0
            future,_ = read_pose()
            pelvis = future['pelvis'].translation
            target = pelvis+unreal.Vector(300,400,200)
            assert agent.call_method('TriggerNNAttack',args=(unreal.Name('slashL'),target,True))
            requested,effective,ghost = agent.call_method('GetNNAttackTarget')
            close(xyz(requested),xyz(target))
            assert abs(math.dist(xyz(pelvis),xyz(effective))-125)<0.001
            assert agent.call_method('SetGlobalHalfAttackTargetRadius',args=(75.0,))
            requested,effective,ghost = agent.call_method('GetNNAttackTarget')
            assert abs(math.dist(xyz(pelvis),xyz(effective))-75)<0.001
            assert peer.call_method('GetGlobalHalfAttackTargetRadius')==75
            near=pelvis+unreal.Vector(20,30,15)
            assert agent.call_method('SetNNAttackTarget',args=(near,))
            close(xyz(agent.call_method('GetNNAttackTarget')[1]),xyz(near))
            assert agent.call_method('SetNNHalfAttackEnabled',args=(False,))
            assert agent.call_method('SetNNAttackTarget',args=(target,))
            close(xyz(agent.call_method('GetNNAttackTarget')[1]),xyz(target))
            assert agent.call_method('SetNNHalfAttackEnabled',args=(True,))
            hit_test['half_frame'] = agent.call_method('GetNNAttackState')[-1]
            hit_test['phase']=5
        elif phase==5:
            attack=agent.call_method('GetNNAttackState')
            if attack is None:
                finish('Half attack ended before a step could be observed'); return
            if attack[-1]<=hit_test['half_frame']+5:return
            future,_=read_pose()
            r,e,g=agent.call_method('GetNNAttackTarget')
            distance=math.dist(xyz(future['pelvis'].translation),xyz(e))
            assert distance<=75.001,(distance,attack)
            hit_test['rows'].append({'half_attack':{'frame':attack[-1], 'radius_cm':75, 'effective_distance_cm':distance,
                'armed':attack[2],'hit':attack[3], 'requested':xyz(r),'effective':xyz(e),'ghost':xyz(g)}})
            finish()
    except Exception:
        finish(traceback.format_exc())


hit_test['handle']=unreal.register_slate_post_tick_callback(tick)
print('Hit-node runtime checks started on NPC lane 1')
