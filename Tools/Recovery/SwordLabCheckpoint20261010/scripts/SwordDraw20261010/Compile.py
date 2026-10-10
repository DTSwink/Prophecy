import unreal,pathlib,shutil
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SwordDraw20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'User Play active'
for name,rel in [('BP','Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'),('Sword','Content/_mygame/sword/A_Sword.uasset')]:
 p=root/rel
 if not (out/(name+'-preserved.uasset')).exists():shutil.copy2(p,out/(name+'-preserved.uasset'))
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.CompileSync')
print('SWORD_HOLSTER_COMPILE_RETURNED')

