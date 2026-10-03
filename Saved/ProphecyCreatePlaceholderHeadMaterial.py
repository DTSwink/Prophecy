import traceback
import unreal


MATERIAL_DIR = "/Game/Prophecy/MetaHumanPipeline"
MATERIAL_NAME = "M_ProphecyPlaceholderHeadSkin"
MATERIAL_PATH = f"{MATERIAL_DIR}/{MATERIAL_NAME}"


def log(message):
    unreal.log(f"[ProphecyHeadMaterial] {message}")


def ensure_material():
    material = unreal.load_asset(MATERIAL_PATH)
    if material is not None:
        log(f"Material already exists: {material.get_path_name()}")
        apply_material_graph(material)
        ensure_skeletal_usage(material)
        return material

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = asset_tools.create_asset(MATERIAL_NAME, MATERIAL_DIR, unreal.Material, unreal.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"Could not create material: {MATERIAL_PATH}")

    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("two_sided", False)

    apply_material_graph(material)
    ensure_skeletal_usage(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(f"Created material: {material.get_path_name()}")
    return material


def apply_material_graph(material):
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)

    skin_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -520, -160
    )
    skin_color.set_editor_property("constant", unreal.LinearColor(0.36, 0.14, 0.06, 1.0))
    unreal.MaterialEditingLibrary.connect_material_property(
        skin_color, "", unreal.MaterialProperty.MP_BASE_COLOR
    )

    low_fill = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -520, -20
    )
    low_fill.set_editor_property("constant", unreal.LinearColor(0.72, 0.24, 0.055, 1.0))
    unreal.MaterialEditingLibrary.connect_material_property(
        low_fill, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    )

    roughness = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -520, 80
    )
    roughness.set_editor_property("r", 0.62)
    unreal.MaterialEditingLibrary.connect_material_property(
        roughness, "", unreal.MaterialProperty.MP_ROUGHNESS
    )

    specular = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -520, 240
    )
    specular.set_editor_property("r", 0.18)
    unreal.MaterialEditingLibrary.connect_material_property(
        specular, "", unreal.MaterialProperty.MP_SPECULAR
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log("Applied tan head material graph")


def ensure_skeletal_usage(material):
    try:
        material.set_editor_property("used_with_skeletal_mesh", True)
        log("Set used_with_skeletal_mesh=True")
    except Exception as exc:
        log(f"Direct skeletal usage flag failed: {exc}")

    for enum_name in ("MATUSAGE_SKELETAL_MESH", "SKELETAL_MESH"):
        try:
            usage = getattr(unreal.MaterialUsage, enum_name)
        except Exception:
            continue

        try:
            unreal.MaterialEditingLibrary.set_material_usage(material, usage)
            log(f"Set material usage via MaterialEditingLibrary: {enum_name}")
        except Exception as exc:
            log(f"MaterialEditingLibrary usage failed for {enum_name}: {exc}")

    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)


try:
    ensure_material()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
