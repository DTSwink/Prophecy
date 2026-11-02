"""Retain the Imperial finish during the existing Stain Blade callback."""
import os,pathlib,unreal
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
mat=unreal.load_asset('/Game/_mygame/spear/M_ImperialSpear');lib=unreal.MaterialEditingLibrary
assert 'BladeBloodDepth' not in [str(x) for x in lib.get_scalar_parameter_names(mat)]
def expr(cls,x,y):return lib.create_material_expression(mat,cls,x,y)
def scalar(name,value,y):
    n=expr(unreal.MaterialExpressionScalarParameter,-1100,y);n.set_editor_property('parameter_name',name);n.set_editor_property('default_value',value);return n
position=expr(unreal.MaterialExpressionPreSkinnedPosition,-1400,900)
interp=expr(unreal.MaterialExpressionVertexInterpolator,-1200,900)
lib.connect_material_expressions(position,'',interp,'')
mask=expr(unreal.MaterialExpressionCustom,-500,1000)
mask.set_editor_property('description','Spear blade depth coverage with the existing seeded blood edge')
mask.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT1)
names=['LocalPosition','Depth','BaseZ','BladeLength','Variation','LateralScale']
inputs=[]
for name in names:
    i=unreal.CustomInput();i.set_editor_property('input_name',name);inputs.append(i)
mask.set_editor_property('inputs',inputs)
mask.set_editor_property('code',(root/'Tools/Blood/SwordDepthEdge.ush').read_text().replace('LocalPosition.y','LocalPosition.x'))
lib.connect_material_expressions(interp,'',mask,'LocalPosition')
for i,(param,name,value) in enumerate([('BladeBloodDepth','Depth',0),('BladeBaseLocalZ','BaseZ',69.29501),('BladeLengthLocal','BladeLength',46.965602),('BladeBloodVariation','Variation',.5),('BladeLateralScale','LateralScale',1)]):
    lib.connect_material_expressions(scalar(param,value,1100+i*180),'',mask,name)
color=expr(unreal.MaterialExpressionVectorParameter,-200,1100);color.set_editor_property('parameter_name','BladeBloodColor');color.set_editor_property('default_value',unreal.LinearColor(.12,.001,.002,1))
rough=scalar('BladeBloodRoughness',.22,2100)
metal=expr(unreal.MaterialExpressionConstant,-200,1600);metal.set_editor_property('r',0)
for i,(prop,blood) in enumerate([(unreal.MaterialProperty.MP_BASE_COLOR,color),(unreal.MaterialProperty.MP_ROUGHNESS,rough),(unreal.MaterialProperty.MP_METALLIC,metal)]):
    old=lib.get_material_property_input_node(mat,prop);output=lib.get_material_property_input_node_output_name(mat,prop)
    blend=expr(unreal.MaterialExpressionLinearInterpolate,200,1000+i*230)
    lib.connect_material_expressions(old,output,blend,'A');lib.connect_material_expressions(blood,'',blend,'B');lib.connect_material_expressions(mask,'',blend,'Alpha');lib.connect_material_property(blend,'',prop)
lib.recompile_material(mat)
assert unreal.EditorAssetLibrary.save_loaded_asset(mat,only_if_is_dirty=False)
print('Spear depth blood layer saved; base atlas, normals, ORM and cavity colors retained.')
