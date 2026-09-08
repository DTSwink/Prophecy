"""Apply the new color correction only to the active temporary skin preview."""
import json
from pathlib import Path
import unreal

lib=unreal.MaterialEditingLibrary
out=Path(unreal.Paths.project_saved_dir()).resolve()/'BossShading/20260908/NeckColor'
root='/Game/_mygame/MetaHumans/BossUEFN/Materials/AORepair'
report=json.loads((out/'color_diffusion.json').read_text())
assert report['mean_boundary_linear_rgb_error']<.01
component=test['component']
head=component.get_material(7)
assert head.get_path_name().startswith('/Engine/Transient.'), 'Do not alter production material during visual test'
task=unreal.AssetImportTask()
task.set_editor_properties(dict(filename=str(out/'T_Boss_NeckColorMatched.png'),destination_path=root,
    destination_name='T_Boss_NeckColorMatched',automated=True,save=False,replace_existing=True))
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
texture=unreal.load_asset(root+'/T_Boss_NeckColorMatched')
texture.set_editor_properties(dict(srgb=True,compression_settings=unreal.TextureCompressionSettings.TC_BC7,
    address_x=unreal.TextureAddress.TA_CLAMP,address_y=unreal.TextureAddress.TA_CLAMP))
previous=lib.get_material_instance_texture_parameter_value(head,'Boss Neck Body Color')
lib.set_material_instance_texture_parameter_value(head,'Boss Neck Body Color',texture)
lib.update_material_instance(head)
assert lib.get_material_instance_texture_parameter_value(head,'Boss Neck Body Color')==texture
test['color_diffusion_preview']={'texture':texture,'previous_texture':previous}
print('DIFFUSION_PREVIEW_ONLY',texture.get_path_name(),'production head material unchanged')
