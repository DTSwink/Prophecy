"""Transient PIE validation; ends Play and never edits/saves assets or global CVars.
Run through Tools/RunUnrealRemote.py with the saved testNN map open, outside PIE.
"""
import builtins
import json
import math
import pathlib
import time
import traceback
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world(), 'Start outside PIE'
library = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
smoothing = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyNNRootWindowLibrary'))
assert library and smoothing
state = dict(start=time.monotonic(), n=0, last=-1, rows=[], samples={})
builtins._prophecy_root_force_test = state


def xyz(v): return [v.x, v.y, v.z]
def subtract(a, b): return [x-y for x, y in zip(a, b)]
def close(a, b, tolerance=1e-4):
    assert math.dist(a, b) < tolerance, (a, b, tolerance)


def velocity(a): return [xyz(v) for v in a.call_method('GetRootVelocity')]
def force(a, linear, angular, dt, acceleration=False):
    return library.call_method('AddRootForceAndTorque', (a, unreal.Vector(*linear), unreal.Vector(*angular), dt, acceleration))


def check_forces(a, label):
    mass, inertia = a.call_method('GetRootImpulseMassProperties')
    before = velocity(a)
    location, rotation = xyz(a.get_root_low_point()), a.get_actor_rotation().yaw
    assert force(a, [120*mass, -60*mass, 999], [20, 30, 2*inertia], .25)
    after = velocity(a)
    close(subtract(after[0], before[0]), [30, -15, 0])
    close(subtract(after[1], before[1]), [0, 0, .5])
    assert force(a, [-20, 40, 500], [12, 34, -1], .5, True)
    close(subtract(velocity(a)[0], after[0]), [-10, 20, 0])
    close(subtract(velocity(a)[1], after[1]), [0, 0, -.5])
    close(xyz(a.get_root_low_point()), location, 1e-9)
    assert a.get_actor_rotation().yaw == rotation
    snapshot = velocity(a)
    for dt in [-1., float('nan'), float('inf')]:
        assert not force(a, [1, 2, 0], [0, 0, 1], dt, True)
    # Python's FVector marshalling sanitizes NaN/Inf vectors to zero; those native
    # input guards cannot be exercised through this Python fixture. Scalar dt can.
    assert not force(a, [100, 0, 0], [0, 0, 1e8], 1, True)
    assert not force(None, [1, 2, 0], [0, 0, 1], .1)
    assert force(a, [1, 2, 0], [0, 0, 1], 0, True)
    for actual, expected in zip(velocity(a), snapshot): close(actual, expected, 1e-9)
    # Same integrated duration split differently; no intervening steering/braking steps.
    deltas = []
    for calls in [30, 60]:
        v = velocity(a)
        for _ in range(calls): assert force(a, [3, -6, 0], [0, 0, .25], 1./calls, True)
        deltas.append([subtract(x, y) for x, y in zip(velocity(a), v)])
    for d in deltas:
        close(d[0], [3, -6, 0]); close(d[1], [0, 0, .25])
    state['rows'].append(dict(force_backend=label, mass_kg=mass, inertia_kg_cm2=inertia,
                              frame_partition_deltas=deltas, rejection_atomic=True))


def check_error(a, label):
    names, future, targets, alpha = a.read_nn_future_world_pose()
    mesh = a.get_pose_reference_mesh()
    linear, angular, total, count = [0.]*3, [0.]*3, 0., 0
    for name, target in zip(names, targets):
        body = a.get_physical_body_state(name)
        if not body or not body[-1]: continue
        actual = body[0]
        mass = mesh.get_bone_mass(name, True)
        if mass <= 0: continue
        count += 1; total += mass
        for j, delta in enumerate(subtract(xyz(actual.translation), xyz(target.translation))): linear[j] += mass*delta
        # Independent Hamilton product actual * conjugate(target), shortest world arc.
        p, q = actual.rotation, target.rotation
        x = -p.w*q.x+p.x*q.w-p.y*q.z+p.z*q.y
        y = -p.w*q.y+p.x*q.z+p.y*q.w-p.z*q.x
        z = -p.w*q.z-p.x*q.y+p.y*q.x+p.z*q.w
        w = p.w*q.w+p.x*q.x+p.y*q.y+p.z*q.z
        norm = math.sqrt(x*x+y*y+z*z+w*w)
        sign = (1 if w >= 0 else -1)/norm
        x,y,z,w = x*sign,y*sign,z*sign,w*sign
        sine = math.sqrt(x*x+y*y+z*z)
        scale = 2*math.atan2(sine,w)/sine if sine > 1e-12 else 2
        for j, value in enumerate([x,y,z]): angular[j] += mass*scale*value
    result = a.call_method('GetMassWeightedPoseError')
    assert result is not None and result[3] == count and count > 0, (label, count, result)
    le, ae = math.dist(xyz(result[0]), linear), math.dist(xyz(result[1]), angular)
    close(xyz(result[0]), linear, .001); close(xyz(result[1]), angular, .0001)
    assert abs(result[2]-total) < .0001
    sample = state['samples'].setdefault(label, dict(n=0, body_count=count, total_mass_kg=total,
        max_linear_difference=0., max_angular_difference=0., max_linear_signal=0., max_angular_signal=0.))
    sample['n'] += 1
    sample['max_linear_difference'] = max(sample['max_linear_difference'], le)
    sample['max_angular_difference'] = max(sample['max_angular_difference'], ae)
    sample['max_linear_signal'] = max(sample['max_linear_signal'], math.dist(linear, [0]*3))
    sample['max_angular_signal'] = max(sample['max_angular_signal'], math.dist(angular, [0]*3))


def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['callback'])
    out = pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootForces.json'
    out.write_text(json.dumps(dict(reason=reason, rows=state['rows'], samples=state['samples']), indent=2))
    if editor.get_game_world(): unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('ROOT_FORCES', reason)


def tick(_):
    try:
        if time.monotonic()-state['start'] > 120: finish('timeout'); return
        world = editor.get_game_world()
        if not world: return
        a = unreal.GameplayStatics.get_player_pawn(world, 0)
        if not isinstance(a, unreal.ProphecyAgent): return
        now = unreal.GameplayStatics.get_time_seconds(world)
        if now == state['last']: return
        state['last'] = now; state['n'] += 1; n = state['n']
        if n == 10:
            a.call_method('StopNNAttack')
            a.set_nn_inference_enabled(True)
            assert smoothing.call_method('SetLocomotionRootWindowSmoothing', (a,1.,1.,1.))
            a.set_locomotion_input(unreal.Vector(), False, unreal.Vector(), 1., 0.)
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
            if not a.is_jolt_physical_animation_enabled(): assert a.enable_jolt_physical_animation()
        if 20 <= n <= 49: check_error(a, 'Jolt Sim')
        if n == 50:
            check_forces(a, 'Jolt Sim')
            assert force(a, [500,0,0], [0,0,2], .5, True)
            state['origin'] = xyz(a.get_root_low_point()); state['yaw'] = a.get_actor_rotation().yaw
            state['peak_yaw_displacement'] = 0.
        if 51 <= n <= 85:
            # The user's live Blueprint may restore steering. Measure the motion
            # before it settles, rather than requiring permanent yaw displacement.
            state['peak_yaw_displacement'] = max(state['peak_yaw_displacement'],
                abs((a.get_actor_rotation().yaw-state['yaw']+180)%360-180))
        if n == 85:
            distance = math.dist(state['origin'], xyz(a.get_root_low_point()))
            angle = state['peak_yaw_displacement']
            assert distance > 1 and angle > 1, (distance, angle)
            state['rows'].append(dict(subsequent_movement_cm=distance, subsequent_yaw_degrees=angle))
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.HALF_SIM)
        if 95 <= n <= 114: check_error(a, 'Jolt Half Sim')
        if n == 115:
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            assert a.call_method('GetMassWeightedPoseError') is None
            check_forces(a, 'Kinematic')
            a.disable_jolt_physical_animation()
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
        if 125 <= n <= 144: check_error(a, 'Chaos Sim')
        if n == 145:
            check_forces(a, 'Chaos Sim')
            a.set_nn_inference_enabled(False)
            assert not force(a, [1,0,0], [0,0,1], .1)
            finish('complete')
    except Exception: finish(traceback.format_exc())


state['callback'] = unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
