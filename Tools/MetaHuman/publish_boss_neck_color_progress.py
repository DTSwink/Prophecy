"""Hold body-matched color over 75% of neck, release over upper 25%."""
import json
import shutil
from pathlib import Path
import unreal

lib=unreal.MaterialEditingLibrary
root='/Game/_mygame/MetaHumans/BossUEFN/Materials/AORepair'
project=Path(unreal.Paths.project_dir()).resolve()
out=project/'Saved/BossShading/20260908/NeckColor'
master=unreal.load_asset(root+'/M_skin_unified_baked_BossAO')
nodes=[o for o in unreal.ObjectIterator(unreal.MaterialExpression) if o.get_outer()==master]
def parameter(name):
    matches=[]
    for o in nodes:
        try:
            if str(o.get_editor_property('parameter_name'))==name:matches.append(o)
        except Exception:pass
    assert len(matches)==1,(name,len(matches))
    return matches[0]
mask=parameter('Boss Neck Distance Mask')
border=parameter('Neck Color Neutral Border Cm')
width=parameter('Neck Color Fade Width Cm')
scale=next(o for o in nodes if isinstance(o,unreal.MaterialExpressionMultiply)
           and mask in lib.get_inputs_for_material_expression(master,o))
safe=next(o for o in nodes if isinstance(o,unreal.MaterialExpressionMax)
          and width in lib.get_inputs_for_material_expression(master,o))
backup=out/'BackupBefore75Percent'
backup.mkdir(exist_ok=True)
backup_file=backup/'M_skin_unified_baked_BossAO.uasset'
assert not backup_file.exists()
shutil.copy2(project/'Content/_mygame/MetaHumans/BossUEFN/Materials/AORepair/M_skin_unified_baked_BossAO.uasset',backup_file)
assert not unreal.EditorAssetLibrary.does_asset_exist(root+'/T_Boss_NeckColorProgress')
task=unreal.AssetImportTask()
task.set_editor_properties(dict(filename=str(out/'T_Boss_NeckColorProgress.png'),destination_path=root,
    destination_name='T_Boss_NeckColorProgress',automated=True,save=False))
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
texture=unreal.load_asset(root+'/T_Boss_NeckColorProgress')
texture.set_editor_properties(dict(srgb=False,compression_settings=unreal.TextureCompressionSettings.TC_GRAYSCALE,
    address_x=unreal.TextureAddress.TA_CLAMP,address_y=unreal.TextureAddress.TA_CLAMP))
# Rename ONLY the color branch's parameter; AO retains its own original mask.
mask.set_editor_properties(dict(parameter_name='Boss Neck Color Progress Mask',texture=texture))
scale.set_editor_property('const_b',1.)
border.set_editor_properties(dict(parameter_name='Neck Color Full Strength Fraction',default_value=.75,
    slider_min=0.,slider_max=.99))
release=lib.create_material_expression(master,unreal.MaterialExpressionOneMinus)
assert lib.connect_material_expressions(border,'',release,'')
assert lib.connect_material_expressions(release,'',safe,'A')
safe.set_editor_property('const_b',.001)
lib.delete_material_expression(master,width)
lib.recompile_material(master)
head=unreal.load_asset('/Game/_mygame/MetaHumans/boss/Face/Materials/MI_Face_Skin_Baked_LOD3_VT')
assert abs(lib.get_material_instance_scalar_parameter_value(head,'Neck Color Full Strength Fraction')-.75)<1e-6
assert lib.get_material_instance_static_switch_parameter_value(head,'Use Boss Neck Color Fade')
assert lib.get_material_instance_texture_parameter_value(head,'Boss Neck Distance Mask').get_name()=='T_Boss_NeckDistance'
assert lib.get_material_instance_texture_parameter_value(head,'Boss Neck Color Progress Mask')==texture
for asset in (texture,master):assert unreal.EditorAssetLibrary.save_loaded_asset(asset,False)
report=json.loads((out/'neck_progress.json').read_text())
report.update({'published':True,'parameter':'Neck Color Full Strength Fraction','AO_mask_unchanged':True,
    'saved_assets':[texture.get_path_name(),master.get_path_name()],
    'normal_specular_bent_normal_preview_tests':'unchanged, transient only',
    'visual_acceptance':'pending user check'})
(out/'neck_progress_publication.json').write_text(json.dumps(report,indent=2))
print('NECK_75_PERCENT_COLOR_PUBLISHED',json.dumps(report))
