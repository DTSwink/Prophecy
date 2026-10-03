import unreal


ASSET_DIR = "/Game/_mygame/Debug"
ASSET_PATH = ASSET_DIR + "/M_PhysicalKinematicReference"


if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
    material = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
else:
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_PhysicalKinematicReference",
        ASSET_DIR,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )

if not material:
    raise RuntimeError("Could not create the physical/kinematic comparison material")

material.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
material.set_editor_property("two_sided", True)

color = unreal.MaterialEditingLibrary.create_material_expression(
    material, unreal.MaterialExpressionVectorParameter, -320, -100
)
color.set_editor_property("parameter_name", "ReferenceColor")
color.set_editor_property("default_value", unreal.LinearColor(0.03, 0.55, 0.95, 1.0))

opacity = unreal.MaterialEditingLibrary.create_material_expression(
    material, unreal.MaterialExpressionScalarParameter, -320, 20
)
opacity.set_editor_property("parameter_name", "ReferenceOpacity")
opacity.set_editor_property("default_value", 0.32)

roughness = unreal.MaterialEditingLibrary.create_material_expression(
    material, unreal.MaterialExpressionConstant, -320, 130
)
roughness.set_editor_property("r", 0.55)

unreal.MaterialEditingLibrary.connect_material_property(
    color, "", unreal.MaterialProperty.MP_BASE_COLOR
)
unreal.MaterialEditingLibrary.connect_material_property(
    opacity, "", unreal.MaterialProperty.MP_OPACITY
)
unreal.MaterialEditingLibrary.connect_material_property(
    roughness, "", unreal.MaterialProperty.MP_ROUGHNESS
)
unreal.MaterialEditingLibrary.set_material_usage(
    material, unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH
)
unreal.MaterialEditingLibrary.layout_material_expressions(material)
unreal.MaterialEditingLibrary.recompile_material(material)
unreal.EditorAssetLibrary.save_loaded_asset(material)
print("REFERENCE_MATERIAL_SAVED", ASSET_PATH)
