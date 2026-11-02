import os,pathlib,unreal
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve Play'
dirty=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert all(p.get_name().startswith('/Game/_mygame/spear/') for p in dirty),[p.get_name() for p in dirty]
for p in unreal.EditorAssetLibrary.list_assets('/Game/_mygame/spear',recursive=True,include_folder=False):
 unreal.EditorAssetLibrary.save_asset(p,only_if_is_dirty=True)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'QUIT_EDITOR')
