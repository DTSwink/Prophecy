import unreal,json,pathlib
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
cdo=unreal.get_default_object(unreal.ProphecyAgent)
r={'map':sub.get_editor_world().get_path_name(),'setter_available':hasattr(cdo,'set_jolt_joint_limit_prediction_enabled'),'getter_available':hasattr(cdo,'is_jolt_joint_limit_prediction_enabled'),'default_enabled':cdo.is_jolt_joint_limit_prediction_enabled(),'pie':bool(sub.get_game_world()),'dirty':[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]}
print(json.dumps(r,indent=2))
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/WideWrist/PredictionNodeVerification.json').write_text(json.dumps(r,indent=2))
