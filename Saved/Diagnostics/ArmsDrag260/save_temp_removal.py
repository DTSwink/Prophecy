import unreal,pathlib,shutil
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
root=pathlib.Path(unreal.Paths.project_dir())
source=root/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
backup=root/'Saved/Diagnostics/ArmsDrag260/BeforeTempNodeRemoval.uasset'
assert not backup.exists(),'Preserve existing backup'
shutil.copy2(source,backup)
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
print('TEMP_NODE_REMOVAL_SAVED; prior disk asset backed up',str(backup))
