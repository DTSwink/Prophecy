"""Create flat debug materials; save only assets created by this script."""
import json
import pathlib
import unreal

folder = '/Game/_mygame/materials/base_colors'
palette = {
    'Green': (0, 255, 0), 'Orange': (255, 128, 0),
    'Red': (255, 0, 0), 'Blue': (0, 0, 255),
    'Purple': (128, 0, 255), 'White': (255, 255, 255),
    'Black': (0, 0, 0), 'Grey': (128, 128, 128),
}
tools = unreal.AssetToolsHelpers.get_asset_tools()
library = unreal.MaterialEditingLibrary
unreal.EditorAssetLibrary.make_directory(folder)
created = []

def linear(channel):
    value = channel / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

for colour, rgb in palette.items():
    for translucent in (False, True):
        name = 'M_' + colour + ('_Translucent' if translucent else '')
        path = folder + '/' + name
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            raise RuntimeError('Refusing to overwrite existing asset: ' + path)
        material = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
        assert material, path
        material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
        material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT if translucent else unreal.BlendMode.BLEND_OPAQUE)
        material.set_editor_property('two_sided', True)
        if translucent:
            material.set_editor_property('translucency_lighting_mode', unreal.TranslucencyLightingMode.TLM_SURFACE)
        colour_node = library.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -320, 0)
        colour_node.set_editor_property('parameter_name', 'Color')
        colour_node.set_editor_property('default_value', unreal.LinearColor(*[linear(c) for c in rgb], 1.0))
        assert library.connect_material_property(colour_node, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
        if translucent:
            opacity_node = library.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -320, 200)
            opacity_node.set_editor_property('parameter_name', 'Opacity')
            opacity_node.set_editor_property('default_value', 0.4)
            assert library.connect_material_property(opacity_node, '', unreal.MaterialProperty.MP_OPACITY)
        for usage in (unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES):
            library.set_material_usage(material, usage)
        library.recompile_material(material)
        assert unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False), path
        assert material.get_editor_property('shading_model') == unreal.MaterialShadingModel.MSM_DEFAULT_LIT
        assert material.get_editor_property('blend_mode') == (unreal.BlendMode.BLEND_TRANSLUCENT if translucent else unreal.BlendMode.BLEND_OPAQUE)
        if translucent:
            assert abs(opacity_node.get_editor_property('default_value') - 0.4) < 1e-6
        created.append(dict(path=path, srgb=list(rgb), opacity=0.4 if translucent else 1.0))

assert len(created) == 16
unreal.EditorAssetLibrary.sync_browser_to_objects([item['path'] for item in created])
report = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/DebugColorMaterials.json'
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(json.dumps(created, indent=2), encoding='utf-8')
print('Created and saved 16 debug materials in ' + folder)
