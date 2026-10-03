import unreal, pathlib, shutil, time
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
src=pathlib.Path(unreal.Paths.project_dir())/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
dst=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'/('PoseBeforeKneeIntermediate-'+time.strftime('%Y%m%d-%H%M%S')+'.uasset')
shutil.copy2(src,dst)
print('PLAY_ACTIVE',bool(ed.get_game_world()))
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
print('KNEE_INTERMEDIATE_POSE_SAVED',src)
