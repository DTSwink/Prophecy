"""Import the 5 cloud-baked face wrinkle textures (MetaHuman head UVs, usable by any MetaHuman-UV head).

Run in the live editor (remote Python), no Play needed:
  & 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/RunUnrealRemote.py Tools/FaceExpressions/import_face_wrinkle_textures.py
Creates new textures only (nothing existing is touched) and does NOT save them.
"""
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
src = root / 'Exports/FaceWrinkles'
dest = '/Game/_mygame/MetaHumans/FaceWrinkles'
files = ['T_Face_WrinkleDetail.png'] + [f'T_Face_WrinkleMasks_{i}.png' for i in range(4)]
for f in files:
    assert (src / f).exists(), src / f
    assert not unreal.EditorAssetLibrary.does_asset_exist(f'{dest}/{f[:-4]}'), f'{f[:-4]} already exists: not overwriting'
tasks = []
for f in files:
    t = unreal.AssetImportTask()
    t.set_editor_properties(dict(filename=str(src / f), destination_path=dest, automated=True, save=False, replace_existing=False))
    tasks.append(t)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
for f in files:
    tex = unreal.load_asset(f'{dest}/{f[:-4]}')
    tex.set_editor_property('srgb', False)
    tex.set_editor_property('compression_settings',
        unreal.TextureCompressionSettings.TC_BC7 if 'Detail' in f else unreal.TextureCompressionSettings.TC_MASKS)
    tex.set_editor_property('lod_group', unreal.TextureGroup.TEXTUREGROUP_CHARACTER)
    tex.post_edit_change()
    print('WRINKLE_TEXTURE', tex.get_path_name(), tex.blueprint_get_size_x(), 'srgb', tex.get_editor_property('srgb'))
print('WRINKLE_TEXTURES_IMPORTED_NOT_SAVED')
