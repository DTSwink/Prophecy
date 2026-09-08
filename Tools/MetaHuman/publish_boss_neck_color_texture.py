"""Update the generated color texture after correcting source UV wrapping."""
import json
from pathlib import Path
import unreal

lib=unreal.MaterialEditingLibrary
root='/Game/_mygame/MetaHumans/BossUEFN/Materials/AORepair'
out=Path(unreal.Paths.project_saved_dir()).resolve()/'BossShading/20260908/NeckColor'
check=json.loads((out/'wrapped_transfer_check.json').read_text())
assert check['new_mean_error']<check['old_mean_error']*.25
source=unreal.load_asset('/Game/_mygame/MetaHumans/boss/Body/Baked/T_Body_BC_VT')
assert source.get_editor_property('address_x')==unreal.TextureAddress.TA_WRAP
assert source.get_editor_property('address_y')==unreal.TextureAddress.TA_WRAP
head=unreal.load_asset('/Game/_mygame/MetaHumans/boss/Face/Materials/MI_Face_Skin_Baked_LOD3_VT')
assert lib.get_material_instance_static_switch_parameter_value(head,'Use Boss Neck AO Fade')
assert unreal.EditorAssetLibrary.does_asset_exist(root+'/T_Boss_NeckBodyColor')
task=unreal.AssetImportTask()
task.filename=str(out/'T_Boss_NeckBodyColor.png')
task.destination_path=root
task.destination_name='T_Boss_NeckBodyColor'
task.automated=True
task.replace_existing=True
task.replace_existing_settings=False
task.save=False
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
texture=unreal.load_asset(root+'/T_Boss_NeckBodyColor')
assert texture.get_editor_property('srgb')
lib.set_material_instance_static_switch_parameter_value(head,'Use Boss Neck Color Fade',True)
lib.update_material_instance(head)
assert lib.get_material_instance_static_switch_parameter_value(head,'Use Boss Neck Color Fade')
assert lib.get_material_instance_static_switch_parameter_value(head,'Use Boss Neck AO Fade')
for asset in (texture,head):
    assert unreal.EditorAssetLibrary.save_loaded_asset(asset,False)
report=json.loads((out/'publication.json').read_text())
report.update({'correction':'Wrap body source UVs (U in [1,2]) before texture lookup; previous clamping sampled dark background',
               'source_addressing_verified':'TA_WRAP in U and V',
               'transfer_check':check,'enabled':True,
               'visual_check':'Original clamped version rejected by user; corrected wrapped transfer awaits user check'})
(out/'publication.json').write_text(json.dumps(report,indent=2))
print('WRAPPED_COLOR_TRANSFER_SAVED',check)
