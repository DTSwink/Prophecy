import json
import pathlib
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
cdo = unreal.get_default_object(unreal.ProphecyAgent)
row = dict(pie=bool(editor.get_game_world()),
    pin_iterations=cdo.get_editor_property('attack_foot_pinning_iterations'),
    gt_headbutt=cdo.get_editor_property('use_gt_headbutt_preparation'),
    blend_seconds=cdo.get_editor_property('headbutt_preparation_blend_seconds'),
    setter=hasattr(cdo, 'set_attack_foot_pinning_iterations'))
assert row['pin_iterations'] == 4 and row['gt_headbutt'] and row['setter']
assert abs(row['blend_seconds'] - 0.1) < 1e-6
blueprint = unreal.EditorAssetLibrary.load_blueprint_class('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
bp = unreal.get_default_object(blueprint)
row['blueprint_pin_iterations'] = bp.get_editor_property('attack_foot_pinning_iterations')
row['dirty'] = [p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
print(json.dumps(row, indent=2))
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/HeadbuttControls.json').write_text(json.dumps(row, indent=2))
