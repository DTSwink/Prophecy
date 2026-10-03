"""Bounded numeric reproduction. Never saves assets or modifies fighter tuning."""
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
import unreal

pose_diag_output = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/PoseIntegrity-20260910'
pose_diag_output.mkdir(exist_ok=True)
pose_diag_path = pose_diag_output / ('poses-' + datetime.now().strftime('%H%M%S') + '.json')
pose_diag_levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not pose_diag_levels.is_in_play_in_editor(), 'Do not replace an existing play session'
pose_diag_state = {'handle': None, 'frames': 0, 'deadline': time.monotonic()+90, 'samples': [], 'metrics': [], 'reference_lengths': {}, 'equip_results': None}
pose_diag_equip = '--equip' in sys.argv
pose_diag_capture = '--capture' in sys.argv

def pose_vec(v):
    return [v.x, v.y, v.z]

def pose_length(v):
    return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)

def sample_fight_pose(delta_seconds):
    state = pose_diag_state
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    try:
        if world and pose_diag_levels.is_in_play_in_editor():
            state['frames'] += 1
            if pose_diag_equip and state['frames'] == 6:
                state['equip_results'] = [a.equip_sword(True) for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)]
            if state['frames'] <= 120:
                rows=[]
                for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
                    mesh = a.get_pose_reference_mesh()
                    bones=[]
                    for index in range(mesh.get_num_bones()):
                        name = mesh.get_bone_name(index)
                        parent = mesh.get_parent_bone(name)
                        pos = mesh.get_socket_location(name)
                        pp = mesh.get_socket_location(parent)
                        body = a.get_physical_body_state(name)
                        row={'name':str(name),'parent':str(parent),'position':pose_vec(pos),'parent_distance_cm':pose_length(pos-pp)}
                        if body:
                            transform, linear, angular, simulated = body
                            bp = transform.translation
                            native_q = transform.rotation
                            visual_q = mesh.get_socket_transform(name).rotation
                            dot = abs(native_q.x*visual_q.x + native_q.y*visual_q.y + native_q.z*visual_q.z + native_q.w*visual_q.w)
                            native_norm_sq = native_q.x*native_q.x+native_q.y*native_q.y+native_q.z*native_q.z+native_q.w*native_q.w
                            visual_norm_sq = visual_q.x*visual_q.x+visual_q.y*visual_q.y+visual_q.z*visual_q.z+visual_q.w*visual_q.w
                            dot /= math.sqrt(native_norm_sq*visual_norm_sq)
                            row.update({'body_position':pose_vec(bp),'body_to_display_cm':pose_length(bp-pos),
                                        'body_to_display_degrees':math.degrees(2*math.acos(min(1.0,dot))),
                                        'linear_cm_s':pose_length(linear),'angular_rad_s':pose_length(angular),'simulated':simulated})
                        bones.append(row)
                    name = a.get_name()
                    jolt = a.is_jolt_physical_animation_enabled()
                    if name not in state['reference_lengths']:
                        state['reference_lengths'][name] = {b['name']:b['parent_distance_cm'] for b in bones}
                    physical = [b for b in bones if 'body_to_display_cm' in b]
                    links = [b for b in physical if b['name'] != 'pelvis']
                    metric = {'frame':state['frames'],'agent':name,'jolt':jolt,'physical_bones':len(physical),
                              'max_body_to_display_cm':max(b['body_to_display_cm'] for b in physical),
                              'max_body_to_display_degrees':max(b['body_to_display_degrees'] for b in physical),
                              'worst_length_bone':max(links,key=lambda b:abs(b['parent_distance_cm']-state['reference_lengths'][name][b['name']]))['name'],
                              'max_link_length_error_cm':max(abs(b['parent_distance_cm']-state['reference_lengths'][name][b['name']]) for b in links)}
                    state['metrics'].append(metric)
                    rows.append({'agent':name,'jolt':jolt,'bones':bones})
                if state['frames'] in (1, 2, 3, 5, 10, 30, 60, 120):
                    state['samples'].append({'frame':state['frames'],'agents':rows})
        if state['frames'] < 120 and time.monotonic() < state['deadline']:
            return
    except Exception as error:
        state['error']=repr(error)
    unreal.unregister_slate_post_tick_callback(state['handle'])
    state['handle']=None
    active = [m for m in state['metrics'] if m['jolt']]
    state['body_alignment_passed'] = (not state.get('error') and state['frames'] == 120 and len(active) >= 236
        and all(m['physical_bones'] == 22 and m['max_body_to_display_cm'] < 0.02
                and m['max_body_to_display_degrees'] < 0.02 for m in active))
    state['max_link_length_error_cm'] = max((m['max_link_length_error_cm'] for m in active), default=None)
    if world:
        try:
            native_path = Path.home() / '.codex/tmp/ProphecyJolt' / (pose_diag_path.stem+'-native.json')
            unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Jolt.VisualStatus '+native_path.as_posix())
            state['native'] = json.loads(native_path.read_text(encoding='utf-8-sig'))
        except Exception as error:
            state['reporting_error'] = repr(error)
    pose_diag_path.write_text(json.dumps({k:v for k,v in state.items() if k not in ('handle','deadline')},indent=2))
    if pose_diag_capture and world and not state.get('error'):
        target = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent) if a.get_name() == 'BP_ProphecyManualPoseAgent_C_1')
        unreal.GameplayStatics.get_player_controller(world,0).set_view_target_with_blend(target,0.0)
        unreal.GameplayStatics.set_game_paused(world,True)
        capture = pose_diag_path.with_suffix('.png')
        unreal.SystemLibrary.execute_console_command(world, 'HighResShot 1 filename="'+capture.as_posix()+'"')
        capture_state = {'handle':None,'deadline':time.monotonic()+5.0}
        def finish_pose_capture(delta):
            if not capture.exists() and time.monotonic()<capture_state['deadline']:
                return
            unreal.unregister_slate_post_tick_callback(capture_state['handle'])
            if pose_diag_levels.is_in_play_in_editor():
                pose_diag_levels.editor_request_end_play()
            print('POSE_CAPTURE_DONE',str(capture),capture.exists())
        capture_state['handle'] = unreal.register_slate_post_tick_callback(finish_pose_capture)
    elif pose_diag_levels.is_in_play_in_editor():
        pose_diag_levels.editor_request_end_play()
    print('POSE_DIAGNOSTIC_DONE', str(pose_diag_path), state.get('error',''))

pose_diag_state['handle']=unreal.register_slate_post_tick_callback(sample_fight_pose)
pose_diag_levels.editor_request_begin_play()
print('POSE_DIAGNOSTIC_REQUESTED', str(pose_diag_path))
