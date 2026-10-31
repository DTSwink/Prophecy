"""Run in an isolated editor/commandlet. Creates only Bodyflip's own material."""
import unreal

PATH = '/Game/BodyflipLab/M_ProjectileVertexColor'
material = unreal.EditorAssetLibrary.load_asset(PATH) if unreal.EditorAssetLibrary.does_asset_exist(PATH) else None
if material is None:
    unreal.EditorAssetLibrary.make_directory('/Game/BodyflipLab')
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        'M_ProjectileVertexColor', '/Game/BodyflipLab', unreal.Material,
        unreal.MaterialFactoryNew())
    assert material is not None, 'Unable to create Bodyflip projectile material'
    library = unreal.MaterialEditingLibrary
    color = library.create_material_expression(material, unreal.MaterialExpressionVertexColor, -300, 0)
    assert library.connect_material_property(color, '', unreal.MaterialProperty.MP_BASE_COLOR)
    roughness = library.create_material_expression(material, unreal.MaterialExpressionConstant, -300, 180)
    roughness.set_editor_property('r', 0.52)
    assert library.connect_material_property(roughness, '', unreal.MaterialProperty.MP_ROUGHNESS)
    library.recompile_material(material)
    assert unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
unreal.log('Bodyflip projectile vertex-color material: ' + material.get_path_name())
