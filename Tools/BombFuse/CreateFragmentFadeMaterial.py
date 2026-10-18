"""Prepare a translucent companion for the bomb's glTF material family only.
Original material/assets remain untouched; runtime copies current uniform values.
"""
import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
folder='/Game/_mygame/BombGenerated/'
lib=unreal.MaterialEditingLibrary
path=folder+'M_BombFragmentFade'
master=unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else unreal.EditorAssetLibrary.duplicate_asset('/InterchangeAssets/gltf/M_Default',path)
master.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
master.set_editor_property('translucency_lighting_mode',unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
nodes=[n for n in unreal.ObjectIterator(unreal.MaterialExpression) if n.get_outer()==master]
parameter=next((n for n in nodes if isinstance(n,unreal.MaterialExpressionScalarParameter) and str(n.get_editor_property('parameter_name'))=='FragmentOpacity'),None)
if not parameter:
 parameter=lib.create_material_expression(master,unreal.MaterialExpressionScalarParameter,200,900)
 parameter.set_editor_property('parameter_name','FragmentOpacity');parameter.set_editor_property('default_value',1.)
 if master.get_editor_property('use_material_attributes'):
  original=lib.get_material_property_input_node(master,unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
  pin=lib.get_material_property_input_node_output_name(master,unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
  setter=lib.create_material_expression(master,unreal.MaterialExpressionSetMaterialAttributes,500,900)
  setter.set_editor_property('desc','Fragment opacity fade')
  setter.set_editor_property('attribute_set_types',[unreal.Guid(0xB8F50FBA,0x2A754EC1,0x9EF672CF,0xEB27BF51)])
  names=list(lib.get_material_expression_input_names(setter))
  assert lib.connect_material_expressions(original,pin,setter,names[0])
  assert lib.connect_material_expressions(parameter,'',setter,names[1])
  assert lib.connect_material_property(setter,'',unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
 else:assert lib.connect_material_property(parameter,'',unreal.MaterialProperty.MP_OPACITY)
lib.recompile_material(master)
assert unreal.EditorAssetLibrary.save_loaded_asset(master)
path=folder+'MI_BombFragmentFade'
instance=unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else unreal.EditorAssetLibrary.duplicate_asset('/InterchangeAssets/gltf/MaterialInstances/MI_Default_Opaque',path)
lib.set_material_instance_parent(instance,master)
overrides=instance.get_editor_property('base_property_overrides')
overrides.set_editor_property('override_blend_mode',False)
instance.set_editor_property('base_property_overrides',overrides)
source=unreal.load_asset('/Game/Fab/CC0_-_Bomb/cc0_bomb/Materials/Bomb')
pressure=unreal.load_asset('/Game/Fab/CC0_-_Bomb/cc0_bomb/Materials/PressureBomb')
for name in lib.get_static_switch_parameter_names(source):
 value=lib.get_material_instance_static_switch_parameter_value(source,name)
 assert not pressure or lib.get_material_instance_static_switch_parameter_value(pressure,name)==value,'Bomb shader permutations differ; prepare a separate companion'
 lib.set_material_instance_static_switch_parameter_value(instance,name,value)
 assert lib.get_material_instance_static_switch_parameter_value(instance,name)==value,str(name)
lib.update_material_instance(instance)
assert unreal.EditorAssetLibrary.save_loaded_asset(instance)
print('Prepared real translucent fade companion; original bomb materials unchanged:',instance.get_path_name())
