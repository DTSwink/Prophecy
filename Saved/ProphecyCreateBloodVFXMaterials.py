import traceback

import unreal


ASSET_DIR = "/Game/Prophecy/Materials"
MATERIAL_PATH = f"{ASSET_DIR}/M_ProphecyBloodVFX_Surface"


def log(message):
    unreal.log(f"[ProphecyBloodVFX] {message}")


def ensure_dir(path):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)


def set_if_present(obj, prop, value):
    try:
        obj.set_editor_property(prop, value)
        return True
    except Exception:
        return False


def create_or_load_material():
    if unreal.EditorAssetLibrary.does_asset_exist(MATERIAL_PATH):
        asset = unreal.EditorAssetLibrary.load_asset(MATERIAL_PATH)
        if isinstance(asset, unreal.Material):
            return asset

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    return tools.create_asset("M_ProphecyBloodVFX_Surface", ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew())


def constant(material, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionConstant, x, y)
    node.set_editor_property("r", value)
    return node


def vector_parameter(material, name, color, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, x, y
    )
    set_if_present(node, "parameter_name", name)
    set_if_present(node, "default_value", color)
    set_if_present(node, "constant", color)
    return node


def constant3(material, color, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, x, y
    )
    set_if_present(node, "constant", color)
    return node


def build_material():
    ensure_dir(ASSET_DIR)
    material = create_or_load_material()
    if not material:
        raise RuntimeError("Could not create blood VFX material")

    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)

    set_if_present(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_if_present(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    set_if_present(material, "shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    set_if_present(material, "two_sided", True)
    set_if_present(material, "use_material_attributes", False)

    vertex_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVertexColor, -560, -130
    )
    roughness = constant(material, 0.48, -520, 70)
    specular = constant(material, 0.22, -520, 170)
    metallic = constant(material, 0.0, -520, 270)
    emissive_scale = constant(material, 0.34, -520, 370)
    emissive = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -260, 245
    )

    unreal.MaterialEditingLibrary.connect_material_property(
        vertex_color, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(vertex_color, "", emissive, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(emissive_scale, "", emissive, "B")
    unreal.MaterialEditingLibrary.connect_material_property(
        emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        roughness, "", unreal.MaterialProperty.MP_ROUGHNESS
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        specular, "", unreal.MaterialProperty.MP_SPECULAR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        metallic, "", unreal.MaterialProperty.MP_METALLIC
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    log(f"Saved {MATERIAL_PATH}")


try:
    build_material()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
