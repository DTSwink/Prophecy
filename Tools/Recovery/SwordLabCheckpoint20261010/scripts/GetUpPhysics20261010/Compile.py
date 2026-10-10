import unreal,pathlib,shutil
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/GetUpPhysics20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'User Play active'
path=root/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
shutil.copy2(path,out/'BP-disk-before.uasset')
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True)
shutil.copy2(path,out/'BP-preserved.uasset')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.CompileSync')
print('GETUP_PHYSICS_COMPILE_RETURNED')
