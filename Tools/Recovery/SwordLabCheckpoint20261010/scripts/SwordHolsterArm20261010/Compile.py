import unreal,pathlib,shutil,hashlib,json
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SwordHolsterArm20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert not ed.get_game_world()
p=root/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
if not (out/'BP-disk-before.uasset').exists():shutil.copy2(p,out/'BP-disk-before.uasset')
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True)
shutil.copy2(p,out/'BP-user-preserved.uasset')
(out/'hashes-before.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [p,root/'Content/testNN.umap',root/'Content/_mygame/sword/A_Sword.uasset']},indent=2),encoding='utf-8')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.CompileSync')
print('SWORD_FIX_COMPILE_RETURNED')
