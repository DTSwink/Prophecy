import unreal,shutil,time
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
root=Path(unreal.Paths.project_dir())
source=root/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
backup=root/'Saved/Diagnostics'/('PoseBeforeElbowBackup-'+time.strftime('%Y%m%d-%H%M%S')+'.uasset')
shutil.copy2(source,backup)
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
print('POSE_BLUEPRINT_SAVED_FOR_REQUESTED_BACKUP',source)
