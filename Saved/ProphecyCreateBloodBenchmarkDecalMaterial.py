import traceback

import unreal


ASSET_DIR = "/Game/Prophecy/Materials"
MATERIAL_PATH = f"{ASSET_DIR}/M_ProphecyBloodBenchmark_Decal"


def log(message):
    unreal.log(f"[ProphecyBloodBenchmarkDecal] {message}")


def ensure_dir(path):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)


def set_if_present(obj, prop, value):
    try:
        obj.set_editor_property(prop, value)
        return True
    except Exception:
        return False


def first_enum_value(enum_cls, names):
    for name in names:
        try:
            return getattr(enum_cls, name)
        except Exception:
            pass
    return None


def constant(material, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionConstant, x, y)
    node.set_editor_property("r", value)
    return node


def constant3(material, color, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, x, y
    )
    set_if_present(node, "constant", color)
    return node


def create_or_load_material():
    if unreal.EditorAssetLibrary.does_asset_exist(MATERIAL_PATH):
        asset = unreal.EditorAssetLibrary.load_asset(MATERIAL_PATH)
        if isinstance(asset, unreal.Material):
            return asset

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    return tools.create_asset("M_ProphecyBloodBenchmark_Decal", ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew())


def build_material():
    ensure_dir(ASSET_DIR)
    material = create_or_load_material()
    if not material:
        raise RuntimeError("Could not create blood benchmark decal material")

    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)

    set_if_present(material, "material_domain", unreal.MaterialDomain.MD_DEFERRED_DECAL)
    set_if_present(material, "blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    set_if_present(material, "shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    set_if_present(material, "two_sided", True)
    decal_blend = first_enum_value(
        unreal.DecalBlendMode,
        [
            "DBM_DBUFFER_COLOR_NORMAL_ROUGHNESS",
            "DBM_DBUFFER_COLOR_ROUGHNESS",
            "DBM_DBUFFER_COLOR",
            "DBM_TRANSLUCENT",
        ],
    )
    if decal_blend is not None:
        set_if_present(material, "decal_blend_mode", decal_blend)

    blood = constant3(material, unreal.LinearColor(0.72, 0.006, 0.003, 1.0), -520, -120)
    opacity = constant(material, 0.92, -520, 20)
    roughness = constant(material, 0.18, -520, 160)
    specular = constant(material, 0.8, -520, 300)

    unreal.MaterialEditingLibrary.connect_material_property(blood, "", unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(opacity, "", unreal.MaterialProperty.MP_OPACITY)
    unreal.MaterialEditingLibrary.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
    unreal.MaterialEditingLibrary.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    log(f"Saved {MATERIAL_PATH}")


try:
    build_material()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
