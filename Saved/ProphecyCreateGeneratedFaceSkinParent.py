import traceback
import unreal


MATERIAL_DIR = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials"
MATERIAL_NAME = "M_ProphecyGeneratedFaceSkin"
MATERIAL_PATH = f"{MATERIAL_DIR}/{MATERIAL_NAME}"

FACE_MATERIALS = [
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD3",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD5to7",
]

TEXTURES = {
    "Basecolor": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor",
    "Normal": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal",
    "Cavity": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Cavity",
}


def log(message):
    unreal.log(f"[ProphecyGeneratedFaceSkin] {message}")


def load_asset(asset_path):
    asset = unreal.load_asset(asset_path)
    if asset is None:
        raise RuntimeError(f"Missing asset: {asset_path}")
    return asset


def set_property_if_available(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception as exc:
        log(f"Could not set {obj.get_class().get_name()}.{name}: {exc}")
        return False


def sampler_type(*candidate_names):
    for candidate_name in candidate_names:
        try:
            return getattr(unreal.MaterialSamplerType, candidate_name)
        except AttributeError:
            continue
    raise RuntimeError(f"Could not resolve sampler type from: {candidate_names}")


def create_texture_parameter(material, name, texture_path, x, y, sampler_type=None):
    expression = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, x, y
    )
    set_property_if_available(expression, "parameter_name", name)
    set_property_if_available(expression, "texture", load_asset(texture_path))
    if sampler_type is not None:
        set_property_if_available(expression, "sampler_type", sampler_type)
    return expression


def create_constant(material, value, x, y):
    expression = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, x, y
    )
    set_property_if_available(expression, "r", value)
    return expression


def apply_material_graph(material):
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)

    basecolor = create_texture_parameter(
        material,
        "Basecolor",
        TEXTURES["Basecolor"],
        -640,
        -220,
        sampler_type("SAMPLERTYPE_VIRTUAL_COLOR", "SAMPLERTYPE_VIRTUALCOLOR"),
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        basecolor, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
    )

    normal = create_texture_parameter(
        material,
        "Normal",
        TEXTURES["Normal"],
        -640,
        -20,
        sampler_type("SAMPLERTYPE_VIRTUAL_NORMAL", "SAMPLERTYPE_VIRTUALNORMAL"),
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        normal, "RGB", unreal.MaterialProperty.MP_NORMAL
    )

    # The generated cavity map keeps the placeholder face from rendering flat while
    # staying independent of the missing MetaHuman optional bake payload.
    cavity = create_texture_parameter(
        material,
        "Cavity",
        TEXTURES["Cavity"],
        -640,
        180,
        sampler_type("SAMPLERTYPE_MASKS"),
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        cavity, "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION
    )

    roughness = create_constant(material, 0.56, -340, 310)
    unreal.MaterialEditingLibrary.connect_material_property(
        roughness, "", unreal.MaterialProperty.MP_ROUGHNESS
    )

    specular = create_constant(material, 0.28, -340, 430)
    unreal.MaterialEditingLibrary.connect_material_property(
        specular, "", unreal.MaterialProperty.MP_SPECULAR
    )

    set_property_if_available(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_property_if_available(material, "two_sided", False)
    set_property_if_available(material, "used_with_skeletal_mesh", True)

    try:
        unreal.MaterialEditingLibrary.set_material_usage(
            material, unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH
        )
    except Exception as exc:
        log(f"Could not set skeletal mesh usage via library: {exc}")

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(f"Applied generated face skin graph: {material.get_path_name()}")


def ensure_material():
    material = unreal.load_asset(MATERIAL_PATH)
    if material is None:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        material = asset_tools.create_asset(
            MATERIAL_NAME, MATERIAL_DIR, unreal.Material, unreal.MaterialFactoryNew()
        )
        if material is None:
            raise RuntimeError(f"Could not create material: {MATERIAL_PATH}")
        log(f"Created material: {material.get_path_name()}")
    else:
        log(f"Updating material: {material.get_path_name()}")

    apply_material_graph(material)
    return material


def relink_face_instances(parent_material):
    for material_path in FACE_MATERIALS:
        material = load_asset(material_path)
        unreal.MaterialEditingLibrary.set_material_instance_parent(material, parent_material)
        log(f"{material.get_name()}.parent -> {parent_material.get_name()}")

        for parameter_name, texture_path in TEXTURES.items():
            unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
                material, parameter_name, load_asset(texture_path)
            )
            log(f"{material.get_name()}.{parameter_name} -> {texture_path.rsplit('/', 1)[-1]}")

        unreal.MaterialEditingLibrary.update_material_instance(material)
        unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)


def main():
    parent_material = ensure_material()
    relink_face_instances(parent_material)
    log("DONE")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
