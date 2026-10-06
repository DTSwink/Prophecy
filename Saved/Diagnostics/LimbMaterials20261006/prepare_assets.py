import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LimbMaterials20261006'
source=p/'neutral_palette.png'
task=unreal.AssetImportTask();task.filename=str(source.resolve());task.destination_path='/Game/_mygame/Materials/LimbColors';task.destination_name='T_LimbPalette';task.automated=True;task.save=False;task.replace_existing=False
if not unreal.EditorAssetLibrary.does_asset_exist('/Game/_mygame/Materials/LimbColors/T_LimbPalette'):
 unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
tex=unreal.load_asset('/Game/_mygame/Materials/LimbColors/T_LimbPalette')
tex.set_editor_property('srgb',False);tex.set_editor_property('filter',unreal.TextureFilter.TF_NEAREST)
tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
tex.set_editor_property('mip_gen_settings',unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
tex.set_editor_property('address_x',unreal.TextureAddress.TA_CLAMP);tex.set_editor_property('address_y',unreal.TextureAddress.TA_CLAMP)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.PrepareLimbColors Audit')
print((p/'prepare.txt').read_text(encoding='utf-8-sig'))
