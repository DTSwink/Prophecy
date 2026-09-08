"""PIE-only NN skinning/pose capture on an isolated native test shell.

Stage one temporary native ProphecyAgent named BossUEFNAxes_Validation_TEMP
with manual_nn_pose_application=True before PIE. Remove it after PIE; never
save the test actor/map. Production Blueprints and their timers stay untouched.
"""
import json
import math
import time
import traceback
from pathlib import Path
import unreal

OUT = Path(unreal.Paths.project_saved_dir()).resolve() / 'BossUEFNCompatible/20260907'
OUT.mkdir(parents=True, exist_ok=True)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world, 'Start PIE first'
agent = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
             if a.get_actor_label() == 'BossUEFNAxes_Validation_TEMP' and a.has_valid_agent_handle())
agent.manual_nn_pose_application = False
unreal.SystemLibrary.execute_console_command(world,'ke ' + agent.get_path_name() + ' SetSimulationMode Kinematic')
agent.set_show_kinematic_debug_mesh(False)
agent.set_all_physical_feedback_tolerances(1000000., 360.)
agent.set_actor_tick_enabled(False)  # Isolate the asset from user BP Tick experiments.
mesh = agent.get_pose_reference_mesh()
physics_asset = mesh.get_editor_property('physics_asset_override') or unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin').get_editor_property('physics_asset')
asset = unreal.load_asset('/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN_Fitted')
mesh.set_skeletal_mesh_asset(asset)
mesh.set_editor_property('override_materials', [])
if physics_asset:
    mesh.set_physics_asset(physics_asset, True)
mesh.set_all_bodies_simulate_physics(False)
mesh.set_all_bodies_physics_blend_weight(0.)
mesh.set_anim_instance_class(unreal.ProphecyNNLocomotionAnimInstance)
pose_id, interval, interpolate = agent.get_nn_pose_data_source()
anim = mesh.get_anim_instance()
anim.agent_id = pose_id
anim.nn_pose_interval_seconds = interval
anim.use_viewer_global_pose_interpolation = interpolate
anim.interpolate_nn_pose = interpolate
mesh.set_visibility(True)
mesh.set_hidden_in_game(False)
mesh.set_forced_lod(1)

# A temporary PIE capture actor renders only this mesh without moving the user's view.
unreal.SystemLibrary.execute_console_command(world, 'summon SceneCapture2D')
capture_actor = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SceneCapture2D)[-1]
capture = capture_actor.get_component_by_class(unreal.SceneCaptureComponent2D)
capture.capture_every_frame = False
capture.capture_on_movement = False
capture.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
capture.primitive_render_mode = unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST
capture.show_only_component(mesh)
capture.fov_angle = 38.
target = unreal.RenderingLibrary.create_render_target2d(world, 700, 1000, unreal.TextureRenderTargetFormat.RTF_RGBA8)
capture.texture_target = target

def xyz(v): return [v.x, v.y, v.z]
def tf(t): return {'position': xyz(t.translation), 'rotation': [t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w], 'scale': xyz(t.scale3d)}

state = {'callback': None, 'phase': -1, 'start': 0., 'next_sample': 0., 'samples': [], 'captures': [], 'pending_image': None}
phases = [('idle',unreal.Vector(),False), ('walk',unreal.Vector(0,1,0),False), ('run',unreal.Vector(0,1,0),True)]

def finish(error=None):
    if state['callback'] is not None:
        unreal.unregister_slate_post_tick_callback(state['callback'])
        state['callback'] = None
    (OUT / 'runtime.json').write_text(json.dumps({'passed': error is None, 'error': error,
        'agent': agent.get_name(), 'mesh': asset.get_path_name(), 'samples': state['samples'], 'captures': state['captures']}, indent=2))
    unreal.log('BOSS_RUNTIME_COMPLETE error=' + str(error))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()

def capture_skin(label):
    bones = {str(mesh.get_bone_name(i)): tf(mesh.get_socket_transform(mesh.get_bone_name(i),
                unreal.RelativeTransformSpace.RTS_COMPONENT)) for i in range(mesh.get_num_bones())}
    dm = unreal.DynamicMesh()
    _, _, outcome = unreal.GeometryScript_SceneUtils.copy_mesh_from_component(mesh, dm,
        unreal.GeometryScriptCopyMeshFromComponentOptions(), False)
    assert outcome == unreal.GeometryScriptOutcomePins.SUCCESS
    positions = []
    for i in range(unreal.GeometryScript_MeshQueries.get_vertex_count(dm)):
        p, valid = unreal.GeometryScript_MeshQueries.get_vertex_position(dm, i)
        assert valid
        positions.append(xyz(p))
    assert all(math.isfinite(v) for p in positions for v in p)
    bounds = [[min(p[i] for p in positions) for i in range(3)], [max(p[i] for p in positions) for i in range(3)]]
    assert max(b-a for a,b in zip(*bounds)) < 400., ('Exploding mesh bounds', bounds)
    (OUT / (label + '_skin.json')).write_text(json.dumps({'bones': bones, 'positions': positions,
        'mesh_world': tf(mesh.get_world_transform()), 'bounds': bounds}))
    origin = mesh.get_world_location()
    look = origin + unreal.Vector(0,0,90)
    camera = origin + unreal.Vector(130,350,120)
    capture.set_world_location_and_rotation(camera, unreal.MathLibrary.find_look_at_rotation(camera,look),False,True)
    capture.capture_scene()
    state['pending_image'] = label
    state['captures'].append({'phase': label, 'vertex_count':len(positions), 'bounds_cm': bounds})

def tick(_delta):
    try:
        if state['pending_image']:
            unreal.RenderingLibrary.export_render_target(world,target,str(OUT),state['pending_image']+'.png')
            state['pending_image'] = None
        now = unreal.GameplayStatics.get_time_seconds(world)
        if state['phase'] < 0 or now - state['start'] >= 2.5:
            state['phase'] += 1
            if state['phase'] >= len(phases):
                finish()
                return
            state['start'] = now
        label, move, run = phases[state['phase']]
        agent.set_locomotion_input(move,run,unreal.Vector(0,1,0),1.,1.)
        assert not mesh.is_simulating_physics('pelvis')
        assert agent.apply_nn_pose_kinematically(0.)
        if now >= state['next_sample']:
            names, future, presented, alpha = agent.read_nn_future_world_pose()
            errors = {str(n): math.dist(xyz(mesh.get_socket_location(n)),xyz(t.translation)) for n,t in zip(names,presented)}
            state['samples'].append({'time': now, 'phase':label, 'root':xyz(agent.get_actor_location()),
                                     'position_errors_cm':errors, 'alpha':alpha})
            state['next_sample'] = now + .25
        if now - state['start'] >= 2.0 and not any(c['phase'] == label for c in state['captures']):
            capture_skin(label)
    except Exception:
        finish(traceback.format_exc())

state['callback'] = unreal.register_slate_post_tick_callback(tick)
print('Boss fitted axes: three short NN pose/skin captures, runtime-only; PIE will stop automatically')
