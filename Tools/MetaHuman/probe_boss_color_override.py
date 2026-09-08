"""Read-only inspect the engine's preconfigured BaseColor override functions."""
import unreal
lib = unreal.MaterialEditingLibrary
master = unreal.load_asset('/Game/_mygame/MetaHumans/BossUEFN/Materials/AORepair/M_skin_unified_baked_BossAO')
for name in ('MatLayerBlend_OverrideBaseColor', 'MatLayerBlend_BaseColorOverride'):
    function = unreal.load_asset('/Engine/Functions/MaterialLayerFunctions/' + name)
    print('FUNCTION', function.get_path_name())
    nodes = [o for o in unreal.ObjectIterator(unreal.MaterialExpression)
             if o.get_outer() == function]
    for node in nodes:
        extra = ''
        if isinstance(node, unreal.MaterialExpressionFunctionInput):
            extra = str(node.get_editor_property('input_name'))
        if isinstance(node, unreal.MaterialExpressionFunctionOutput):
            extra = str(node.get_editor_property('output_name'))
        print(node.get_name(), extra, list(lib.get_material_expression_input_names(node)),
              [x.get_name() if x else None for x in lib.get_inputs_for_material_expression(master,node)])
head = unreal.load_asset('/Game/_mygame/MetaHumans/boss/Face/Materials/MI_Face_Skin_Baked_LOD3_VT')
print('AO enabled',lib.get_material_instance_static_switch_parameter_value(head,'Use Boss Neck AO Fade'))
print('COLOR enabled',lib.get_material_instance_static_switch_parameter_value(head,'Use Boss Neck Color Fade'))
