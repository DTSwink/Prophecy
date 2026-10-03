import unreal
library = unreal.MaterialEditingLibrary
folder = '/Game/_mygame/materials/base_colors/'
count = 0
for colour in ['Green', 'Orange', 'Red', 'Blue', 'Purple', 'White', 'Black', 'Grey']:
    for version in ['Opaque', 'Translucent']:
        material = unreal.EditorAssetLibrary.load_asset(folder + 'M_Debug_' + colour + '_' + version)
        assert material
        emissive = library.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        assert emissive
        value = emissive.get_editor_property('default_value')
        # Deleting this expression clears its emissive connection as well.
        library.delete_material_expression(material, emissive)
        node = library.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -320, 0)
        node.set_editor_property('parameter_name', 'Color')
        node.set_editor_property('default_value', value)
        assert library.connect_material_property(node, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
        material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
        if version == 'Translucent':
            material.set_editor_property('translucency_lighting_mode', unreal.TranslucencyLightingMode.TLM_SURFACE)
            opacity = library.get_material_property_input_node(material, unreal.MaterialProperty.MP_OPACITY)
            assert abs(opacity.get_editor_property('default_value') - 0.4) < 1e-6
        assert library.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR) is None
        assert library.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR) == node
        library.recompile_material(material)
        assert unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
        count += 1
print('Saved', count, 'standard lit Base Color materials; no emissive connection; translucent opacity 0.4.')
