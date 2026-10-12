"""Record presented NN locomotion in owned PIE; never writes editor assets.

180 moving game ticks settle, then 720 ticks at the authored 60 Hz. Captures
the full lab skeleton in the managed root frame, without physics noise.
"""
import argparse
import json
import pathlib
import time
import traceback
import unreal

p = argparse.ArgumentParser()
p.add_argument('--motion', choices=['walk', 'run'], required=True)
p.add_argument('--output', default='Saved/Diagnostics/LocomotionCapture20261012')
p.add_argument('--collect-dead', action='store_true', help='Exercise removed-agent lanes before recording')
args = p.parse_args()
input_length = .4 if args.motion == 'walk' else 1.
root = pathlib.Path(unreal.Paths.project_dir())
out = root / args.output
out.mkdir(parents=True, exist_ok=True)
names = json.loads((root/'Labs/SwordHolsterLab/data/motions.json').read_text(encoding='utf-8'))['names']
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'User Play left untouched'
s = dict(world=None, start=time.monotonic(), last=-1, rows=[], warmup=180, duration=720)
old_fps = unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')


def pose(t):
    a, q = t.translation, t.rotation
    return [a.x, a.y, a.z, q.x, q.y, q.z, q.w]


def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['callback'])
    if s['world'] and ed.get_game_world() == s['world']:
        level.editor_request_end_play()
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), f't.MaxFPS {old_fps}')
    result = {k:v for k,v in s.items() if k not in ['world','actor','direction','callback','start']}
    result.update(reason=reason, motion=args.motion, names=names, fps=60,
                  source='Unreal presented NN, kinematic, skeletal mesh frame, neutral gaze', restored_fps=old_fps,
                  checkpoint='run', movement_input_length=input_length, speed_scale=1.)
    (out/(args.motion+'.json')).write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
    print('LOCOMOTION_CAPTURE', args.motion, reason, len(s['rows']))


def tick(_):
    try:
        if time.monotonic()-s['start'] > 180:
            return finish('timeout')
        world = ed.get_game_world()
        if not world:
            if s['world']: finish('world ended externally')
            return
        s['world'] = world
        actor = unreal.GameplayStatics.get_player_pawn(world,0)
        if not isinstance(actor,unreal.ProphecyAgent): return
        n = int(actor.get_editor_property('absolute tick debug'))
        if n == s['last']: return
        s['last'] = n
        if n < 6: return
        if 'actor' not in s:
            s['actor'] = actor
            s['input_tick'] = n
            s['direction'] = actor.get_actor_forward_vector()
            assert actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            for field in ['disable gaze debug','disable auto locomotion debug']:
                unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',(actor,field,True))
            actor.set_upper_nn_gaze(0.,0.)
            actor.set_locomotion_walk_checkpoint_speed_threshold(-1.)
            for other in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent):
                if other != actor: other.destroy_actor()
            for obstacle in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor):
                if obstacle.get_actor_label() == 'Cube':
                    for c in obstacle.get_components_by_class(unreal.PrimitiveComponent):
                        c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                    obstacle.set_actor_enable_collision(False)
        # Prevent the existing tick-25 D/S fixture; only temporary PIE equipment.
        if n <= s['input_tick']+30: actor.hide_sword()
        actor.set_locomotion_input(s['direction'] * input_length,True,s['direction'],1.,1.)
        elapsed = n-s['input_tick']
        if args.collect_dead and elapsed>=60 and not s.get('collected_dead'):
            unreal.SystemLibrary.collect_garbage()
            s['collected_dead']=n
        if elapsed < s['warmup']: return
        assert abs(actor.upper_nn_gaze_yaw_normalized)<1.e-6 and abs(actor.upper_nn_gaze_pitch_normalized)<1.e-6, 'Blueprint changed neutral capture gaze'
        walk_weight, run_weight = actor.get_locomotion_checkpoint_weights()
        assert walk_weight < 1.e-6 and abs(run_weight-1.) < 1.e-6, 'Capture must use the run checkpoint'
        bone_names, future, presented, alpha = actor.read_nn_future_world_pose()
        lookup = {str(k):t for k,t in zip(bone_names,presented)}
        # PhysicalMesh is detached in this manual rig. Use the ordinary Mesh:
        # it carries the actor heading plus the capsule-to-skeleton height.
        frame = actor.mesh.get_world_transform()
        assert all(k in lookup for k in names if k != 'root')
        values = [pose(unreal.MathLibrary.make_relative_transform(lookup[k] if k != 'root' else frame,frame)) for k in names]
        velocity, facing, running = actor.get_locomotion_state()
        s['rows'].append(dict(tick=n,pose=values,root=pose(actor.get_actor_transform()),frame=pose(frame),alpha=alpha,mode=str(actor.get_simulation_mode()),locomotion=str(actor.get_locomotion_state()),checkpoint_weights=[walk_weight,run_weight],speed_cm_s=velocity.length(),running=running))
        if len(s['rows']) == 1:
            s['nn_bones'] = list(lookup)
            s['socket_bones'] = [k for k in names if k not in lookup]
        if elapsed >= s['warmup']+s['duration']: finish('captured')
    except Exception:
        finish(traceback.format_exc())


unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'t.MaxFPS 60')
s['callback'] = unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('LOCOMOTION_CAPTURE_STARTED',args.motion)
