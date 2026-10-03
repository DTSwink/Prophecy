import json
import unreal

assert pose_diag_state['frames'] == 120 and pose_diag_state['handle'] is None
assert not pose_diag_path.exists()
pose_diag_state['reporting_error'] = 'The optional native status destination was unquoted; recovered the completed numerical samples from memory.'
pose_diag_path.write_text(json.dumps({k:v for k,v in pose_diag_state.items() if k not in ('handle','deadline')},indent=2))
if unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor():
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
active = [m for m in pose_diag_state['metrics'] if m['jolt']]
print(json.dumps({'alignment_passed':pose_diag_state['body_alignment_passed'], 'frames':pose_diag_state['frames'], 'max_offset_cm':max(m['max_body_to_display_cm'] for m in active), 'max_angle_degrees':max(m['max_body_to_display_degrees'] for m in active), 'max_link_error_cm':pose_diag_state['max_link_length_error_cm'], 'physical_counts':sorted(set(m['physical_bones'] for m in active)), 'error':pose_diag_state.get('error')}, indent=2))
