"""Publish a head-only BaseColor transition using transferred body collar color.

User requested to perform visual validation themselves. This changes only the
isolated Boss master and its current head instance; source textures/mesh stay put.
"""
import json
from pathlib import Path
import unreal

# Use the engine's serialized override function: do not construct or resize
# Get/SetMaterialAttributes nodes through Python (their pins may stay invalid).

lib=unreal.MaterialEditingLibrary
root='/Game/_mygame/MetaHumans/BossUEFN/Materials/AORepair'
master=unreal.load_asset(root+'/M_skin_unified_baked_BossAO')
head=unreal.load_asset('/Game/_mygame/MetaHumans/boss/Face/Materials/MI_Face_Skin_Baked_LOD3_VT')
body=unreal.load_asset('/Game/_mygame/MetaHumans/boss/Body/Materials/MI_Body_Baked_VT')
assert 'Use Boss Neck Color Fade' not in [str(n) for n in lib.get_static_switch_parameter_names(master)]
source=lib.get_material_property_input_node(master,unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
source_pin=lib.get_material_property_input_node_output_name(master,unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
assert source
override_function=unreal.load_asset('/Engine/Functions/MaterialLayerFunctions/MatLayerBlend_OverrideBaseColor')
assert override_function
assert lib.get_material_instance_static_switch_parameter_value(head,'Use Boss Neck AO Fade')
out=Path(unreal.Paths.project_saved_dir()).resolve()/'BossShading/20260908/NeckColor'
task=unreal.AssetImportTask()
task.filename=str(out/'T_Boss_NeckBodyColor.png')
task.destination_path=root
task.destination_name='T_Boss_NeckBodyColor'
task.automated=True
task.save=False
if not unreal.EditorAssetLibrary.does_asset_exist(root+'/T_Boss_NeckBodyColor'):
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
texture=unreal.load_asset(root+'/T_Boss_NeckBodyColor')
assert texture
texture.set_editor_property('srgb',True)
texture.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_BC7)
texture.set_editor_property('address_x',unreal.TextureAddress.TA_CLAMP)
texture.set_editor_property('address_y',unreal.TextureAddress.TA_CLAMP)
distance_texture=unreal.load_asset(root+'/T_Boss_NeckDistance')
created=[]
def make(kind,**props):
    o=lib.create_material_expression(master,kind)
    created.append(o)
    for k,v in props.items():o.set_editor_property(k,v)
    return o
def link(a,ap,b,bp):
    assert lib.connect_material_expressions(a,ap,b,bp), (a.get_name(),ap,b.get_name(),bp)

color=make(unreal.MaterialExpressionTextureSampleParameter2D,parameter_name='Boss Neck Body Color',group='Boss Neck Color',texture=texture,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
mask=make(unreal.MaterialExpressionTextureSampleParameter2D,parameter_name='Boss Neck Distance Mask',group='Boss Neck Color',texture=distance_texture,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
cm=make(unreal.MaterialExpressionMultiply,const_b=10.)
link(mask,'R',cm,'A')
border=make(unreal.MaterialExpressionScalarParameter,parameter_name='Neck Color Neutral Border Cm',group='Boss Neck Color',default_value=.2,slider_min=0.,slider_max=1.)
width=make(unreal.MaterialExpressionScalarParameter,parameter_name='Neck Color Fade Width Cm',group='Boss Neck Color',default_value=5.,slider_min=.1,slider_max=9.)
subtract=make(unreal.MaterialExpressionSubtract)
link(cm,'',subtract,'A');link(border,'',subtract,'B')
safe=make(unreal.MaterialExpressionMax,const_b=.01)
link(width,'',safe,'A')
ratio=make(unreal.MaterialExpressionDivide)
link(subtract,'',ratio,'A');link(safe,'',ratio,'B')
alpha=make(unreal.MaterialExpressionSaturate)
link(ratio,'',alpha,'')
weight=make(unreal.MaterialExpressionOneMinus)
link(alpha,'',weight,'')
override=make(unreal.MaterialExpressionMaterialFunctionCall,material_function=override_function)
link(source,source_pin or '',override,'Material')
link(color,'RGB',override,'NewBaseColor')
link(weight,'',override,'Mask')
switch=make(unreal.MaterialExpressionStaticSwitchParameter,parameter_name='Use Boss Neck Color Fade',group='Boss Neck Color',default_value=False)
link(override,'',switch,'True');link(source,source_pin or '',switch,'False')
assert lib.connect_material_property(switch,'',unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
lib.recompile_material(master)
# UE5.7 returns false even when this setter succeeds. Read back the value.
lib.set_material_instance_static_switch_parameter_value(head,'Use Boss Neck Color Fade',True)
lib.update_material_instance(head)
assert lib.get_material_instance_static_switch_parameter_value(head,'Use Boss Neck Color Fade')
assert not lib.get_material_instance_static_switch_parameter_value(body,'Use Boss Neck Color Fade')
assert lib.get_material_instance_static_switch_parameter_value(head,'Use Boss Neck AO Fade')
for asset in (texture,master,head):
    assert unreal.EditorAssetLibrary.save_loaded_asset(asset,False)
report={'head':head.get_path_name(),'enabled':True,'width_cm':5.,'neutral_border_cm':.2,
        'override_function':override_function.get_path_name(),
        'method':'Lerp(body collar texture transferred to head UVs, original final BaseColor, distance fade)',
        'saved_assets':[a.get_path_name() for a in (texture,master,head)],
        'unchanged':'Mesh, UVs, rig, source color textures, AO settings, other material attributes, shared MetaHuman master',
        'visual_check':'Left to user as requested; not claimed visually accepted'}
(out/'publication.json').write_text(json.dumps(report,indent=2))
print('BOSS_NECK_COLOR_PUBLISHED',json.dumps(report))
