"""Executed in the isolated scene material builder's namespace."""
assert pathlib.Path(unreal.Paths.get_project_file_path()).stem == 'MainMenuSceneLab'
m=material('M_Mannequin')
m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_CLEAR_COAT)
m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_OPAQUE)
m.set_editor_property('tangent_space_normal',True)
LIB.set_material_usage(m,unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
uv=node(m,unreal.MaterialExpressionTextureCoordinate)
base_normal=node(m,unreal.MaterialExpressionTextureSample,
 texture=unreal.load_asset('/Game/Characters/UEFN_Mannequin/Textures/T_UEFN_Mannequin_N'),
 sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
gravity=node(m,unreal.MaterialExpressionTransform,
 transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD,
 transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_TANGENT)
assert LIB.connect_material_expressions(vector(m,(0,0,-1)),'',gravity,'')
wet=scalar(m,.65,'WetAmount')
inputs={'UV':uv,'Gravity':gravity,'Wet':wet,
 'Density':scalar(m,.55,'BeadDensity'),'Size':scalar(m,1,'BeadSize'),
 'T':scalar(m,0,'WetTime'),'Speed':scalar(m,.3,'RunoffSpeed'),
 'Trails':scalar(m,.45,'TrailAmount')}
code=(pathlib.Path(__file__).parent/'wet_common.ush').read_text()
code+='''
float4 field=0;
[branch] if(Wet>.0001 && Density>.0001){
 SceneWetSurface wetSurface;
 field=wetSurface.evaluate(UV,Gravity.xy,Density,Size,T,Speed,Trails,abs(ddx(UV))+abs(ddy(UV)));
}
return field;
'''
field=custom(m,code,inputs,unreal.CustomMaterialOutputType.CMOT_FLOAT4)
normal=custom(m,'return normalize(float3(Base.xy-Field.xy*.30*Strength*saturate(Wet),max(.1,Base.z)));',
 {'Base':base_normal,'Field':field,'Strength':scalar(m,.65,'BeadStrength'),'Wet':wet})
prop(normal,unreal.MaterialProperty.MP_NORMAL)
# The original surface retains its own normal beneath the water layer.
bottom=node(m,unreal.MaterialExpressionClearCoatNormalCustomOutput)
assert LIB.connect_material_expressions(base_normal,'RGB',bottom,'')
color=custom(m,'return float3(.12,.112,.105)*lerp(1,.93,saturate(Wet));',{'Wet':wet})
prop(color,unreal.MaterialProperty.MP_BASE_COLOR)
prop(scalar(m,.48),unreal.MaterialProperty.MP_METALLIC)
prop(scalar(m,.5),unreal.MaterialProperty.MP_SPECULAR)
prop(scalar(m,.28,'BodyRoughness'),unreal.MaterialProperty.MP_ROUGHNESS)
coat=custom(m,'return saturate(Wet)*(.16+.84*saturate(Field.w));',
 {'Wet':wet,'Field':field},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
coat.set_editor_property('desc','WetCoatMask')
coat_roughness=custom(m,'return lerp(.11,.055,saturate(Field.w));',
 {'Field':field},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
coat_roughness.set_editor_property('desc','WetCoatRoughness')
# UE hides the clearcoat property enum from Python. The lab's small native
# finalizer connects only these two named outputs, recompiles and saves.
receipt=out/'wet-material.json'
if receipt.exists():receipt.unlink()
unreal.SystemLibrary.execute_console_command(None,'Scene.FinalizeWetMaterial')
assert receipt.exists() and json.loads(receipt.read_text())['saved'], 'Wet material finalizer did not save successfully'
print('WET_MATERIAL_READY uv_anchored_beads_and_gravity_runoff')
