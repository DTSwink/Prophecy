"""Reload only the saved spear Blueprint and inspect its persisted defaults."""
import os,pathlib,unreal
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
bp=unreal.load_asset('/Game/_mygame/spear/A_Spear')
result=unreal.EditorLoadingAndSavingUtils.reload_packages([bp.get_outermost()])
print('Spear disk reload:',result)
assert result[0] and not str(result[1]),result
(out/'disk-reload.txt').write_text(str(result))
bp=unreal.load_asset('/Game/_mygame/spear/A_Spear')
for name in ['K2Node_CallFunction_1','K2Node_CallFunction_18','K2Node_CallFunction_117']:
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'GETALL K2Node_CallFunction EnabledState OUTER='+bp.get_path_name()+':EventGraph NAME='+name)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'GETALL Blueprint Status NAME=A_Spear')
exec((pathlib.Path(unreal.Paths.project_dir())/'Tools/SpearAsset/verify_unreal_spear_asset.py').read_text(),globals())
