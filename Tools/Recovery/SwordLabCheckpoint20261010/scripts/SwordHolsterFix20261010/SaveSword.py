import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordHolsterFix20261010'
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert (p/'graph-before.txt').read_bytes()==(p/'graph-after.txt').read_bytes()
assert unreal.EditorAssetLibrary.save_loaded_asset(unreal.load_asset('/Game/_mygame/sword/A_Sword'),only_if_is_dirty=True)
print('Unchanged sword graph saved after compiler dirtied its package')
