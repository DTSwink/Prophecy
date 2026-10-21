"""Create an opt-in blade-depth companion; do not assign or edit the original material."""
import unreal

path='/Game/_mygame/sword/geometry/M_Sword_BloodDepth'
assert not unreal.EditorAssetLibrary.does_asset_exist(path), 'Inspect existing material before replacing'
source=unreal.load_asset('/Game/_mygame/sword/geometry/M_Sword')
assert source and not source.get_editor_property('use_material_attributes')
material=unreal.EditorAssetLibrary.duplicate_asset(source.get_path_name().split('.')[0],path)
lib=unreal.MaterialEditingLibrary

def expr(cls,x,y):
    return lib.create_material_expression(material,cls,x,y)

def scalar(name,value,x,y):
    n=expr(unreal.MaterialExpressionScalarParameter,x,y)
    n.set_editor_property('parameter_name',name)
    n.set_editor_property('default_value',value)
    n.set_editor_property('group','Blade Blood')
    return n

position=expr(unreal.MaterialExpressionPreSkinnedPosition,0,1200)
interpolator=expr(unreal.MaterialExpressionVertexInterpolator,220,1200)
assert lib.connect_material_expressions(position,'',interpolator,'')
depth=scalar('BladeBloodDepth',0.,0,1400)
base=scalar('BladeBaseLocalZ',0.,0,1600)
length=scalar('BladeLengthLocal',1.,0,1800)
mask=expr(unreal.MaterialExpressionCustom,400,1400)
mask.set_editor_property('description','Blood coverage from tip toward hilt in mesh local coordinates')
mask.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT1)
inputs=[]
for name in ['LocalPosition','Depth','BaseZ','BladeLength']:
    item=unreal.CustomInput();item.set_editor_property('input_name',name);inputs.append(item)
mask.set_editor_property('inputs',inputs)
mask.set_editor_property('code','float d = saturate(Depth); float t = (LocalPosition.z - BaseZ) / max(abs(BladeLength), 0.0001); return (d > 0 && t >= 0 && t >= 1-d) ? 1.0 : 0.0;')
for node,name in [(interpolator,'LocalPosition'),(depth,'Depth'),(base,'BaseZ'),(length,'BladeLength')]:
    assert lib.connect_material_expressions(node,'',mask,name)

color=expr(unreal.MaterialExpressionVectorParameter,400,1700)
color.set_editor_property('parameter_name','BladeBloodColor')
color.set_editor_property('default_value',unreal.LinearColor(.12,.001,.002,1.))
color.set_editor_property('group','Blade Blood')
roughness=scalar('BladeBloodRoughness',.22,400,1900)
metallic=expr(unreal.MaterialExpressionConstant,400,2100)
metallic.set_editor_property('r',0.)
for prop,blood,y,default in [
    (unreal.MaterialProperty.MP_BASE_COLOR,color,1400,.5),
    (unreal.MaterialProperty.MP_ROUGHNESS,roughness,1650,.5),
    (unreal.MaterialProperty.MP_METALLIC,metallic,1900,0.)]:
    old=lib.get_material_property_input_node(material,prop)
    output=lib.get_material_property_input_node_output_name(material,prop) if old else ''
    if old is None:
        old=expr(unreal.MaterialExpressionConstant,600,y+120)
        old.set_editor_property('r',default)
    blend=expr(unreal.MaterialExpressionLinearInterpolate,900,y)
    assert lib.connect_material_expressions(old,output,blend,'A')
    assert lib.connect_material_expressions(blood,'',blend,'B')
    assert lib.connect_material_expressions(mask,'',blend,'Alpha')
    assert lib.connect_material_property(blend,'',prop)
lib.recompile_material(material)
assert unreal.EditorAssetLibrary.save_loaded_asset(material)
print('Created',path,'Original material and sword unchanged.')
