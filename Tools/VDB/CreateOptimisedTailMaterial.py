"""Prepare only our material companion; leave the Zibra plugin material unchanged."""
import unreal

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None, 'Preserve user Play'
path = '/Game/_mygame/animations/VDB/M_ProphecyVDBOptimisedTail'
lib = unreal.MaterialEditingLibrary
material = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else unreal.EditorAssetLibrary.duplicate_asset('/ZibraVDB/Materials/ZibraVDBBBoxRender', path)
assert material
nodes = [n for n in unreal.ObjectIterator(unreal.MaterialExpressionCustom) if n.get_outer() == material and 'ZibraLib.MarchVolume(' in n.get_editor_property('code')]
assert len(nodes) == 1
node = nodes[0]
code = node.get_editor_property('code')
if 'ProphecyCachedDensityRatio' not in code:
    assert code.lstrip().startswith('return')
    inputs = list(node.get_editor_property('inputs'))
    ratio = unreal.CustomInput()
    ratio.set_editor_property('input_name', 'ProphecyCachedDensityRatio')
    inputs.append(ratio)
    node.set_editor_property('inputs', inputs)
    parameter = lib.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -300, 1200)
    parameter.set_editor_property('parameter_name', 'ProphecyCachedDensityRatio')
    parameter.set_editor_property('default_value', 1.)
    assert lib.connect_material_expressions(parameter, '', node, 'ProphecyCachedDensityRatio')
    node.set_editor_property('code', 'float4 cachedResult = ' + code.lstrip()[len('return'):].strip() + '\ncachedResult.rgb *= ProphecyCachedDensityRatio;\nreturn cachedResult;')
lib.recompile_material(material)
assert unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
print('Prepared optimised 3D tail companion:', material.get_path_name())
