import math
import os
import struct
import zlib

import unreal

ASSET_DIR = "/Game/Prophecy/Materials"
TEXTURE_DIR = "/Game/Prophecy/Textures"
SAVED_DIR = unreal.Paths.project_saved_dir()
GROUND_TEXTURE_SOURCE = os.path.join(SAVED_DIR, "ProphecyGrassGroundNoise.png")
DIRT_MASK_TEXTURE_SOURCE = os.path.join(SAVED_DIR, "ProphecyDirtPatchMask.png")
DIRT_ALBEDO_TEXTURE_SOURCE = os.path.join(SAVED_DIR, "ProphecyDirtMossClean.png")
GRASS_FIELD_DARK = unreal.LinearColor(0.050, 0.145, 0.032, 1.0)
GRASS_FIELD_LIGHT = unreal.LinearColor(0.140, 0.285, 0.060, 1.0)
GRASS_FIELD_INSTANCE_DARK = unreal.LinearColor(0.74, 0.88, 0.72, 1.0)
GRASS_FIELD_INSTANCE_LIGHT = unreal.LinearColor(1.05, 1.07, 0.88, 1.0)
GRASS_FAR_HILLS_DARK = unreal.LinearColor(0.120, 0.355, 0.000, 1.0)
GRASS_FAR_HILLS_LIGHT = unreal.LinearColor(0.160, 0.455, 0.015, 1.0)
GRASS_TERRAIN_DARK = unreal.LinearColor(0.060, 0.155, 0.045, 1.0)
GRASS_TERRAIN_LIGHT = unreal.LinearColor(0.150, 0.275, 0.085, 1.0)
GRASS_TERRAIN_BASE = unreal.LinearColor(0.150, 0.265, 0.070, 1.0)


def ensure_dir(path):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)


def stable_noise(x, y, seed):
    n = (x * 374761393 + y * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177
    n = (n ^ (n >> 16)) & 0xFFFFFFFF
    return n / 4294967295.0


def smooth_noise(x, y, scale, seed):
    fx = x / scale
    fy = y / scale
    x0 = math.floor(fx)
    y0 = math.floor(fy)
    tx = fx - x0
    ty = fy - y0
    tx = tx * tx * (3.0 - 2.0 * tx)
    ty = ty * ty * (3.0 - 2.0 * ty)
    a = stable_noise(x0, y0, seed)
    b = stable_noise(x0 + 1, y0, seed)
    c = stable_noise(x0, y0 + 1, seed)
    d = stable_noise(x0 + 1, y0 + 1, seed)
    return (a + (b - a) * tx) + ((c + (d - c) * tx) - (a + (b - a) * tx)) * ty


def write_rgba_png(path, width, height, pixel_fn):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row.extend(pixel_fn(x, y))
        rows.append(bytes(row))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png.extend(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
    png.extend(chunk(b"IDAT", zlib.compress(b"".join(rows), 9)))
    png.extend(chunk(b"IEND", b""))
    with open(path, "wb") as handle:
        handle.write(png)


def ensure_ground_texture_source():
    if os.path.exists(GROUND_TEXTURE_SOURCE):
        return

    def pixel(x, y):
        n = (
            smooth_noise(x, y, 18.0, 19) * 0.52
            + smooth_noise(x, y, 57.0, 41) * 0.34
            + smooth_noise(x, y, 141.0, 73) * 0.14
        )
        value = int(max(0.0, min(1.0, n)) * 255.0)
        return (value, value, value, 255)

    write_rgba_png(GROUND_TEXTURE_SOURCE, 1024, 1024, pixel)


def ensure_dirt_mask_texture_source():
    if os.path.exists(DIRT_MASK_TEXTURE_SOURCE):
        return

    def pixel(x, y):
        n = (
            smooth_noise(x, y, 44.0, 107) * 0.42
            + smooth_noise(x, y, 116.0, 131) * 0.40
            + smooth_noise(x, y, 310.0, 173) * 0.18
        )
        softened = max(0.0, min(1.0, (n - 0.36) / 0.34))
        value = int(softened * 255.0)
        return (value, value, value, 255)

    write_rgba_png(DIRT_MASK_TEXTURE_SOURCE, 1024, 1024, pixel)


def ensure_dirt_albedo_texture_source():
    if os.path.exists(DIRT_ALBEDO_TEXTURE_SOURCE):
        return

    def pixel(x, y):
        n = (
            smooth_noise(x, y, 22.0, 311) * 0.28
            + smooth_noise(x, y, 72.0, 349) * 0.34
            + smooth_noise(x, y, 190.0, 383) * 0.38
        )
        moss = max(0.0, min(1.0, (n - 0.34) / 0.46))
        brown = (92, 66, 34)
        olive = (85, 95, 38)
        r = int(brown[0] + (olive[0] - brown[0]) * moss)
        g = int(brown[1] + (olive[1] - brown[1]) * moss)
        b = int(brown[2] + (olive[2] - brown[2]) * moss)
        return (r, g, b, 255)

    write_rgba_png(DIRT_ALBEDO_TEXTURE_SOURCE, 1024, 1024, pixel)


def import_texture_asset(source_path, destination_name, srgb):
    ensure_dir(TEXTURE_DIR)
    asset_path = f"{TEXTURE_DIR}/{destination_name}"
    existing_texture = unreal.EditorAssetLibrary.load_asset(asset_path)
    if existing_texture and os.environ.get("PROPHECY_FORCE_TEXTURE_REIMPORT", "0") != "1":
        set_if_present(existing_texture, "srgb", srgb)
        unreal.EditorAssetLibrary.save_loaded_asset(existing_texture)
        return existing_texture

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", source_path)
    task.set_editor_property("destination_path", TEXTURE_DIR)
    task.set_editor_property("destination_name", destination_name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = unreal.EditorAssetLibrary.load_asset(asset_path)
    if texture:
        set_if_present(texture, "srgb", srgb)
        unreal.EditorAssetLibrary.save_loaded_asset(texture)
    return texture


def import_ground_texture():
    ensure_ground_texture_source()
    return import_texture_asset(GROUND_TEXTURE_SOURCE, "T_ProphecyGrassGroundNoise", True)


def import_dirt_mask_texture():
    ensure_dirt_mask_texture_source()
    return import_texture_asset(DIRT_MASK_TEXTURE_SOURCE, "T_ProphecyDirtPatchMask", False)


def import_dirt_albedo_texture():
    ensure_dirt_albedo_texture_source()
    return import_texture_asset(DIRT_ALBEDO_TEXTURE_SOURCE, "T_ProphecyDirtMossClean", True)


def get_or_create_material(name):
    asset_path = f"{ASSET_DIR}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        material = unreal.EditorAssetLibrary.load_asset(asset_path)
        if material:
            return material
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    return tools.create_asset(name, ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew())


def set_if_present(obj, prop, value):
    try:
        obj.set_editor_property(prop, value)
        return True
    except Exception:
        return False


def create_vector_parameter(material, name, default_value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, x, y
    )
    set_if_present(node, "parameter_name", name)
    set_if_present(node, "default_value", default_value)
    return node


def create_scalar_parameter(material, name, default_value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, x, y
    )
    set_if_present(node, "parameter_name", name)
    set_if_present(node, "default_value", default_value)
    return node


def create_blood_mask_sample(material, world_xy, x, y):
    center = create_vector_parameter(material, "BloodMaskCenter", unreal.LinearColor(0.0, 700.0, 0.0, 0.0), x, y)
    center_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, x + 205, y
    )
    set_if_present(center_xy, "r", True)
    set_if_present(center_xy, "g", True)
    set_if_present(center_xy, "b", False)
    set_if_present(center_xy, "a", False)
    relative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, x + 395, y - 60
    )
    inv_extent = create_scalar_parameter(material, "BloodMaskInvExtent", 1.0 / (12000.0 * 2.0), x + 205, y + 110)
    scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, x + 590, y - 55
    )
    uv_bias = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant2Vector, x + 590, y + 65
    )
    set_if_present(uv_bias, "r", 0.5)
    set_if_present(uv_bias, "g", 0.5)
    uv = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, x + 780, y - 15
    )
    texture = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, x + 975, y - 25
    )
    set_if_present(texture, "parameter_name", "BloodMask")
    default_texture = unreal.EditorAssetLibrary.load_asset("/Engine/EngineResources/Black.Black")
    if not default_texture:
        default_texture = unreal.EditorAssetLibrary.load_asset("/Engine/EngineResources/DefaultTexture.DefaultTexture")
    if default_texture:
        set_if_present(texture, "texture", default_texture)
    mask = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, x + 1175, y - 25
    )
    set_if_present(mask, "r", True)
    set_if_present(mask, "g", False)
    set_if_present(mask, "b", False)
    set_if_present(mask, "a", False)
    core = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, x + 1175, y + 80
    )
    set_if_present(core, "r", False)
    set_if_present(core, "g", True)
    set_if_present(core, "b", False)
    set_if_present(core, "a", False)

    unreal.MaterialEditingLibrary.connect_material_expressions(center, "", center_xy, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(world_xy, "", relative, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(center_xy, "", relative, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(relative, "", scaled, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(inv_extent, "", scaled, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(scaled, "", uv, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(uv_bias, "", uv, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(uv, "", texture, "UVs")
    unreal.MaterialEditingLibrary.connect_material_expressions(texture, "", mask, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(texture, "", core, "None")
    return mask, core


def rebuild_grass_material():
    material = get_or_create_material("M_ProphecyGrass_LitVertexColor")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)

    set_if_present(material, "two_sided", False)
    set_if_present(material, "used_with_instanced_static_meshes", True)
    set_if_present(material, "b_used_with_instanced_static_meshes", True)
    set_if_present(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_if_present(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    set_if_present(material, "dithered_lod_transition", True)
    try:
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    except Exception:
        pass
    try:
        usage = unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES
        unreal.MaterialEditingLibrary.set_material_usage(material, usage)
    except Exception:
        pass

    vertex_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVertexColor, -420, -60
    )
    emissive_fill = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -420, 35
    )
    emissive_fill.set_editor_property("r", 1.65)
    emissive = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -190, 5
    )
    roughness = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -420, 130
    )
    roughness.set_editor_property("r", 0.82)
    specular = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -420, 220
    )
    specular.set_editor_property("r", 0.08)
    subsurface = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -420, 320
    )
    subsurface.set_editor_property("constant", unreal.LinearColor(0.26, 0.42, 0.16, 1.0))

    unreal.MaterialEditingLibrary.connect_material_property(
        vertex_color, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        vertex_color, "RGB", emissive, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        emissive_fill, "", emissive, "B"
    )
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
        subsurface, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def rebuild_ground_material():
    material = get_or_create_material("M_ProphecyGrassGround")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    ground_texture = import_ground_texture()
    dirt_mask_texture = import_dirt_mask_texture()
    dirt_albedo_texture = import_dirt_albedo_texture()

    set_if_present(material, "two_sided", False)
    set_if_present(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_if_present(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    set_if_present(material, "is_sky", False)
    set_if_present(material, "b_is_sky", False)
    try:
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    except Exception:
        pass

    base = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -920, -60
    )
    set_if_present(base, "parameter_name", "GroundBaseColor")
    set_if_present(base, "default_value", unreal.LinearColor(0.56, 0.55, 0.50, 1.0))
    base_output = ""
    noise_scale = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, -720, -190
    )
    set_if_present(noise_scale, "parameter_name", "GroundNoiseScale")
    set_if_present(noise_scale, "default_value", 1.0 / 18000.0)
    noise_uv = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -525, -155
    )
    noise_texture = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, -335, -170
    )
    set_if_present(noise_texture, "parameter_name", "GroundNoiseTexture")
    if ground_texture:
        set_if_present(noise_texture, "texture", ground_texture)
    noise_strength = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, -335, -35
    )
    set_if_present(noise_strength, "parameter_name", "GroundNoiseStrength")
    set_if_present(noise_strength, "default_value", 0.55)
    ground_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, -145, -105
    )
    roughness = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -920, 260
    )
    roughness.set_editor_property("r", 0.92)
    specular = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -920, 350
    )
    specular.set_editor_property("r", 0.04)
    world_position = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionWorldPosition, -920, 60
    )
    world_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -720, 60
    )
    set_if_present(world_xy, "r", True)
    set_if_present(world_xy, "g", True)
    set_if_present(world_xy, "b", False)
    set_if_present(world_xy, "a", False)
    dirt_color = create_vector_parameter(material, "DirtColor", unreal.LinearColor(0.520, 0.360, 0.180, 1.0), -920, 470)
    dirt_patch_scale = create_scalar_parameter(material, "DirtPatchScale", 1.0 / 14000.0, -720, 460)
    dirt_uv = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -525, 455
    )
    dirt_texture = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, -335, 450
    )
    set_if_present(dirt_texture, "parameter_name", "DirtPatchTexture")
    if dirt_mask_texture:
        set_if_present(dirt_texture, "texture", dirt_mask_texture)
    dirt_albedo_scale = create_scalar_parameter(material, "DirtTextureScale", 1.0 / 1600.0, -720, 645)
    dirt_albedo_uv = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -525, 645
    )
    dirt_albedo_sample = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, -335, 710
    )
    set_if_present(dirt_albedo_sample, "parameter_name", "DirtMossTexture")
    if dirt_albedo_texture:
        set_if_present(dirt_albedo_sample, "texture", dirt_albedo_texture)
    dirt_texture_strength = create_scalar_parameter(material, "DirtTextureStrength", 1.00, 40, 355)
    dirt_texture_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 230, 330
    )
    dirt_mask = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -145, 455
    )
    set_if_present(dirt_mask, "r", False)
    set_if_present(dirt_mask, "g", True)
    set_if_present(dirt_mask, "b", False)
    set_if_present(dirt_mask, "a", False)
    dirt_patch_threshold = create_scalar_parameter(material, "DirtPatchThreshold", -1.0, -335, 570)
    dirt_patch_contrast = create_scalar_parameter(material, "DirtPatchContrast", 1.00, -145, 610)
    dirt_mask_offset = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 40, 475
    )
    dirt_mask_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 230, 475
    )
    dirt_zero_const = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 230, 675
    )
    dirt_zero_const.set_editor_property("r", 0.0)
    dirt_one_const = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 420, 675
    )
    dirt_one_const.set_editor_property("r", 1.0)
    dirt_minus_one_const = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 610, 1065
    )
    dirt_minus_one_const.set_editor_property("r", -1.0)
    dirt_patch_nonnegative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMax, 420, 475
    )
    dirt_patch_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMin, 610, 475
    )
    camera_position = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionCameraPositionWS, -920, 715
    )
    camera_distance = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionDistance, -720, 705
    )
    dirt_fade_start = create_scalar_parameter(material, "DirtFadeStartCm", 900.0, -720, 840)
    dirt_fade_inv_range = create_scalar_parameter(material, "DirtFadeInvRange", 1.0 / 6500.0, -525, 885)
    dirt_distance_offset = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, -525, 725
    )
    dirt_distance_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -335, 725
    )
    one_for_distance = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -335, 835
    )
    one_for_distance.set_editor_property("r", 1.0)
    dirt_distance_inverse = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, -145, 725
    )
    dirt_distance_nonnegative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMax, 40, 725
    )
    dirt_distance_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMin, 230, 725
    )
    camera_vector = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionCameraVectorWS, -920, 1040
    )
    vertex_normal = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVertexNormalWS, -920, 1145
    )
    dirt_view_dot = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionDotProduct, -720, 1085
    )
    dirt_view_dot_negative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -525, 1085
    )
    dirt_view_dot_abs = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMax, -335, 1085
    )
    dirt_view_min = create_scalar_parameter(material, "DirtViewMin", 0.00, -525, 1210)
    dirt_view_scale = create_scalar_parameter(material, "DirtViewScale", 10.00, -335, 1250)
    dirt_view_offset = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, -335, 1085
    )
    dirt_view_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -145, 1085
    )
    dirt_view_nonnegative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMax, 40, 1085
    )
    dirt_view_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMin, 230, 1085
    )
    dirt_patch_distance_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 610, 605
    )
    dirt_patch_view_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 805, 760
    )
    dirt_strength = create_scalar_parameter(material, "DirtStrength", 1.00, 805, 910)
    dirt_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1000, 790
    )
    dirt_ground_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 1190, 230
    )
    shadow_center = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -920, 160
    )
    set_if_present(shadow_center, "parameter_name", "GroundShadowMaskCenter")
    set_if_present(shadow_center, "default_value", unreal.LinearColor(0.0, 900.0, 0.0, 0.0))
    shadow_center_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -720, 160
    )
    set_if_present(shadow_center_xy, "r", True)
    set_if_present(shadow_center_xy, "g", True)
    set_if_present(shadow_center_xy, "b", False)
    set_if_present(shadow_center_xy, "a", False)
    shadow_relative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, -525, 95
    )
    shadow_inv_extent = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, -720, 270
    )
    set_if_present(shadow_inv_extent, "parameter_name", "GroundShadowMaskInvExtent")
    set_if_present(shadow_inv_extent, "default_value", 1.0 / (6000.0 * 2.0))
    shadow_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -335, 105
    )
    uv_bias = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant2Vector, -335, 225
    )
    set_if_present(uv_bias, "r", 0.5)
    set_if_present(uv_bias, "g", 0.5)
    shadow_uv = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, -145, 145
    )
    shadow_texture = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, 40, 130
    )
    set_if_present(shadow_texture, "parameter_name", "GroundShadowMask")
    default_shadow_texture = unreal.EditorAssetLibrary.load_asset("/Engine/EngineResources/DefaultTexture.DefaultTexture")
    if default_shadow_texture:
        set_if_present(shadow_texture, "texture", default_shadow_texture)
    shadow_mask = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, 230, 135
    )
    set_if_present(shadow_mask, "r", True)
    set_if_present(shadow_mask, "g", False)
    set_if_present(shadow_mask, "b", False)
    set_if_present(shadow_mask, "a", False)
    shadow_strength = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, 230, 235
    )
    set_if_present(shadow_strength, "parameter_name", "GroundShadowMaskStrength")
    set_if_present(shadow_strength, "default_value", 0.0)
    shadow_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 420, 190
    )
    shadow_tint = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, 40, -35
    )
    set_if_present(shadow_tint, "parameter_name", "GroundShadowMaskTint")
    set_if_present(shadow_tint, "default_value", unreal.LinearColor(0.08, 0.09, 0.085, 1.0))
    shadowed_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 420, -15
    )
    final_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 620, 15
    )
    blood_mask, blood_core = create_blood_mask_sample(material, world_xy, 805, -260)
    blood_strength = create_scalar_parameter(material, "BloodStrength", 0.0, 1000, -375)
    blood_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1190, -335
    )
    blood_color = create_vector_parameter(material, "BloodColor", unreal.LinearColor(0.235, 0.016, 0.010, 1.0), 1190, -220)
    blood_surface_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 1385, -250
    )
    blood_wet_strength = create_scalar_parameter(material, "BloodWetStrength", 0.0, 1000, -85)
    blood_core_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1190, -65
    )
    blood_dark_color = create_vector_parameter(material, "BloodDarkColor", unreal.LinearColor(0.070, 0.003, 0.003, 1.0), 1385, -70)
    blood_final_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 1585, -155
    )

    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_position, "", world_xy, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_center, "", shadow_center_xy, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_xy, "", noise_uv, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        noise_scale, "", noise_uv, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        noise_uv, "", noise_texture, "UVs"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        base, base_output, ground_color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        noise_texture, "RGB", ground_color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        noise_strength, "", ground_color, "Alpha"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_xy, "", dirt_uv, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_patch_scale, "", dirt_uv, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_uv, "", dirt_texture, "UVs"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_xy, "", dirt_albedo_uv, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_albedo_scale, "", dirt_albedo_uv, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_albedo_uv, "", dirt_albedo_sample, "UVs"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_color, "", dirt_texture_color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_albedo_sample, "RGB", dirt_texture_color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_texture_strength, "", dirt_texture_color, "Alpha"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_texture, "", dirt_mask, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_mask, "", dirt_mask_offset, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_patch_threshold, "", dirt_mask_offset, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_mask_offset, "", dirt_mask_scaled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_patch_contrast, "", dirt_mask_scaled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_mask_scaled, "", dirt_patch_nonnegative, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_zero_const, "", dirt_patch_nonnegative, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_patch_nonnegative, "", dirt_patch_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_one_const, "", dirt_patch_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        camera_position, "", camera_distance, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_position, "", camera_distance, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        camera_distance, "", dirt_distance_offset, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_fade_start, "", dirt_distance_offset, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_distance_offset, "", dirt_distance_scaled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_fade_inv_range, "", dirt_distance_scaled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        one_for_distance, "", dirt_distance_inverse, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_distance_scaled, "", dirt_distance_inverse, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_distance_inverse, "", dirt_distance_nonnegative, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_zero_const, "", dirt_distance_nonnegative, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_distance_nonnegative, "", dirt_distance_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_one_const, "", dirt_distance_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        camera_vector, "", dirt_view_dot, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        vertex_normal, "", dirt_view_dot, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_view_dot, "", dirt_view_dot_negative, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_minus_one_const, "", dirt_view_dot_negative, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_view_dot, "", dirt_view_dot_abs, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_view_dot_negative, "", dirt_view_dot_abs, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_view_dot_abs, "", dirt_view_offset, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_view_min, "", dirt_view_offset, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_view_offset, "", dirt_view_scaled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_view_scale, "", dirt_view_scaled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_view_scaled, "", dirt_view_nonnegative, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_zero_const, "", dirt_view_nonnegative, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_view_nonnegative, "", dirt_view_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_one_const, "", dirt_view_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_patch_alpha, "", dirt_patch_distance_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_distance_alpha, "", dirt_patch_distance_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_patch_distance_alpha, "", dirt_patch_view_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_view_alpha, "", dirt_patch_view_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_patch_view_alpha, "", dirt_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_strength, "", dirt_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        ground_color, "", dirt_ground_color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_texture_color, "", dirt_ground_color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_alpha, "", dirt_ground_color, "Alpha"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_xy, "", shadow_relative, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_center_xy, "", shadow_relative, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_relative, "", shadow_scaled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_inv_extent, "", shadow_scaled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_scaled, "", shadow_uv, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        uv_bias, "", shadow_uv, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_uv, "", shadow_texture, "UVs"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_texture, "", shadow_mask, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_mask, "", shadow_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_strength, "", shadow_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_ground_color, "", shadowed_color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_tint, "", shadowed_color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dirt_ground_color, "", final_color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadowed_color, "", final_color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_alpha, "", final_color, "Alpha"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_mask, "", blood_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_strength, "", blood_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        final_color, "", blood_surface_color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_color, "", blood_surface_color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_alpha, "", blood_surface_color, "Alpha"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_core, "", blood_core_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_wet_strength, "", blood_core_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_surface_color, "", blood_final_color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_dark_color, "", blood_final_color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_core_alpha, "", blood_final_color, "Alpha"
    )

    unreal.MaterialEditingLibrary.connect_material_property(
        blood_final_color, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        blood_final_color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        roughness, "", unreal.MaterialProperty.MP_ROUGHNESS
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        specular, "", unreal.MaterialProperty.MP_SPECULAR
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def rebuild_sky_material():
    material = get_or_create_material("M_ProphecySky_Unlit")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)

    set_if_present(material, "two_sided", True)
    set_if_present(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_if_present(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    try:
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    except Exception:
        pass

    color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -300, -60
    )
    color.set_editor_property("constant", unreal.LinearColor(0.48, 0.60, 0.64, 1.0))

    unreal.MaterialEditingLibrary.connect_material_property(
        color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    )
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def rebuild_shared_terrain_material():
    material = get_or_create_material("M_ProphecyGrassTerrainShared")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    ground_texture_asset = import_ground_texture()

    set_if_present(material, "two_sided", False)
    set_if_present(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_if_present(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    set_if_present(material, "is_sky", False)
    set_if_present(material, "b_is_sky", False)
    try:
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    except Exception:
        pass

    world_position = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionWorldPosition, -980, 80
    )
    world_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -780, 80
    )
    set_if_present(world_xy, "r", True)
    set_if_present(world_xy, "g", True)
    set_if_present(world_xy, "b", False)
    set_if_present(world_xy, "a", False)
    terrain_center = create_vector_parameter(material, "TerrainCenter", unreal.LinearColor(0.0, 700.0, 0.0, 0.0), -980, 205)
    terrain_center_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -780, 205
    )
    set_if_present(terrain_center_xy, "r", True)
    set_if_present(terrain_center_xy, "g", True)
    set_if_present(terrain_center_xy, "b", False)
    set_if_present(terrain_center_xy, "a", False)
    terrain_relative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, -570, 115
    )
    terrain_inv_extent = create_scalar_parameter(material, "TerrainInvExtent", 1.0 / (86000.0 * 2.0), -570, 245)
    terrain_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -360, 135
    )
    uv_bias = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant2Vector, -360, 265
    )
    set_if_present(uv_bias, "r", 0.5)
    set_if_present(uv_bias, "g", 0.5)
    terrain_uv = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, -145, 170
    )
    terrain_texture = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, 85, -80
    )
    set_if_present(terrain_texture, "parameter_name", "TerrainBakedColorTexture")
    if ground_texture_asset:
        set_if_present(terrain_texture, "texture", ground_texture_asset)
    vertex_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVertexColor, 85, 80
    )
    diagnostic_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 285, -35
    )

    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_position, "", world_xy, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        terrain_center, "", terrain_center_xy, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_xy, "", terrain_relative, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        terrain_center_xy, "", terrain_relative, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        terrain_relative, "", terrain_scaled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        terrain_inv_extent, "", terrain_scaled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        terrain_scaled, "", terrain_uv, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        uv_bias, "", terrain_uv, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        terrain_uv, "", terrain_texture, "UVs"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        terrain_texture, "RGB", diagnostic_color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        vertex_color, "", diagnostic_color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        diagnostic_color, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        diagnostic_color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def rebuild_field_grass_still_material():
    material = get_or_create_material("M_ProphecyGrass_UnlitField")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)

    set_if_present(material, "two_sided", True)
    set_if_present(material, "used_with_instanced_static_meshes", True)
    set_if_present(material, "b_used_with_instanced_static_meshes", True)
    set_if_present(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_if_present(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    set_if_present(material, "is_sky", False)
    set_if_present(material, "b_is_sky", False)
    try:
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    except Exception:
        pass
    try:
        usage = unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES
        unreal.MaterialEditingLibrary.set_material_usage(material, usage)
    except Exception:
        pass

    dark_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -300, -60
    )
    dark_color.set_editor_property("constant", GRASS_FIELD_INSTANCE_DARK)
    light_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -300, 60
    )
    light_color.set_editor_property("constant", GRASS_FIELD_INSTANCE_LIGHT)
    random = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionPerInstanceRandom, -300, 180
    )
    color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, -60, 20
    )
    root_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -520, -240
    )
    root_color.set_editor_property("constant", unreal.LinearColor(0.010, 0.045, 0.010, 1.0))
    tip_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -520, -145
    )
    tip_color.set_editor_property("constant", unreal.LinearColor(0.155, 0.365, 0.066, 1.0))
    grass_gradient = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, -60, -190
    )
    blade_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 160, -35
    )
    world_position = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionWorldPosition, -720, 295
    )
    world_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -520, 295
    )
    set_if_present(world_xy, "r", True)
    set_if_present(world_xy, "g", True)
    set_if_present(world_xy, "b", False)
    set_if_present(world_xy, "a", False)
    shadow_center = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -720, 390
    )
    set_if_present(shadow_center, "parameter_name", "GrassShadowMaskCenter")
    set_if_present(shadow_center, "default_value", unreal.LinearColor(0.0, 700.0, 0.0, 0.0))
    shadow_center_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -520, 390
    )
    set_if_present(shadow_center_xy, "r", True)
    set_if_present(shadow_center_xy, "g", True)
    set_if_present(shadow_center_xy, "b", False)
    set_if_present(shadow_center_xy, "a", False)
    shadow_relative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, -340, 330
    )
    shadow_inv_extent = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, -520, 500
    )
    set_if_present(shadow_inv_extent, "parameter_name", "GrassShadowMaskInvExtent")
    set_if_present(shadow_inv_extent, "default_value", 1.0 / (6400.0 * 2.0))
    shadow_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -145, 335
    )
    uv_bias = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant2Vector, -145, 455
    )
    set_if_present(uv_bias, "r", 0.5)
    set_if_present(uv_bias, "g", 0.5)
    shadow_uv = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, 40, 375
    )
    shadow_texture = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, 235, 360
    )
    set_if_present(shadow_texture, "parameter_name", "GrassShadowMask")
    default_shadow_texture = unreal.EditorAssetLibrary.load_asset("/Engine/EngineResources/DefaultTexture.DefaultTexture")
    if default_shadow_texture:
        set_if_present(shadow_texture, "texture", default_shadow_texture)
    shadow_mask = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, 430, 365
    )
    set_if_present(shadow_mask, "r", True)
    set_if_present(shadow_mask, "g", False)
    set_if_present(shadow_mask, "b", False)
    set_if_present(shadow_mask, "a", False)
    shadow_strength = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, 430, 465
    )
    set_if_present(shadow_strength, "parameter_name", "GrassShadowMaskStrength")
    set_if_present(shadow_strength, "default_value", 0.88)
    shadow_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 610, 420
    )
    shadow_tint = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, 165, 145
    )
    set_if_present(shadow_tint, "parameter_name", "GrassShadowMaskTint")
    set_if_present(shadow_tint, "default_value", unreal.LinearColor(0.16, 0.28, 0.12, 1.0))
    shadowed_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 430, 115
    )
    final_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 805, 130
    )

    unreal.MaterialEditingLibrary.connect_material_expressions(dark_color, "", color, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(light_color, "", color, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(random, "", color, "Alpha")
    unreal.MaterialEditingLibrary.connect_material_expressions(world_position, "", world_xy, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(shadow_center, "", shadow_center_xy, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(world_xy, "", shadow_relative, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(shadow_center_xy, "", shadow_relative, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(shadow_relative, "", shadow_scaled, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(shadow_inv_extent, "", shadow_scaled, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(shadow_scaled, "", shadow_uv, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(uv_bias, "", shadow_uv, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(shadow_uv, "", shadow_texture, "UVs")
    unreal.MaterialEditingLibrary.connect_material_expressions(shadow_texture, "", shadow_mask, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(shadow_mask, "", shadow_alpha, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(shadow_strength, "", shadow_alpha, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(color, "", shadowed_color, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(shadow_tint, "", shadowed_color, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(color, "", final_color, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(shadowed_color, "", final_color, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(shadow_alpha, "", final_color, "Alpha")

    unreal.MaterialEditingLibrary.connect_material_property(final_color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(final_color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def rebuild_field_grass_material():
    material = get_or_create_material("M_ProphecyGrass_UnlitField")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    wind_texture_asset = import_ground_texture()

    set_if_present(material, "two_sided", True)
    set_if_present(material, "used_with_instanced_static_meshes", True)
    set_if_present(material, "b_used_with_instanced_static_meshes", True)
    set_if_present(material, "blend_mode", unreal.BlendMode.BLEND_MASKED)
    set_if_present(material, "dither_opacity_mask", True)
    set_if_present(material, "opacity_mask_clip_value", 0.333)
    set_if_present(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    set_if_present(material, "is_sky", False)
    set_if_present(material, "b_is_sky", False)
    try:
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    except Exception:
        pass
    try:
        usage = unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES
        unreal.MaterialEditingLibrary.set_material_usage(material, usage)
    except Exception:
        pass

    dark_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -300, -60
    )
    dark_color.set_editor_property("constant", GRASS_FIELD_INSTANCE_DARK)
    light_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -300, 60
    )
    light_color.set_editor_property("constant", GRASS_FIELD_INSTANCE_LIGHT)
    random = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionPerInstanceRandom, -300, 180
    )
    color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, -60, 20
    )
    root_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -520, -240
    )
    root_color.set_editor_property("constant", unreal.LinearColor(0.010, 0.045, 0.010, 1.0))
    tip_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -520, -145
    )
    tip_color.set_editor_property("constant", unreal.LinearColor(0.155, 0.365, 0.066, 1.0))
    grass_gradient = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, -60, -190
    )
    blade_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 160, -35
    )
    world_position = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionWorldPosition, -720, 295
    )
    world_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -520, 295
    )
    set_if_present(world_xy, "r", True)
    set_if_present(world_xy, "g", True)
    set_if_present(world_xy, "b", False)
    set_if_present(world_xy, "a", False)
    shadow_center = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -720, 390
    )
    set_if_present(shadow_center, "parameter_name", "GrassShadowMaskCenter")
    set_if_present(shadow_center, "default_value", unreal.LinearColor(0.0, 700.0, 0.0, 0.0))
    shadow_center_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -520, 390
    )
    set_if_present(shadow_center_xy, "r", True)
    set_if_present(shadow_center_xy, "g", True)
    set_if_present(shadow_center_xy, "b", False)
    set_if_present(shadow_center_xy, "a", False)
    shadow_relative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, -340, 330
    )
    shadow_inv_extent = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, -520, 500
    )
    set_if_present(shadow_inv_extent, "parameter_name", "GrassShadowMaskInvExtent")
    set_if_present(shadow_inv_extent, "default_value", 1.0 / (6400.0 * 2.0))
    shadow_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -145, 335
    )
    uv_bias = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant2Vector, -145, 455
    )
    set_if_present(uv_bias, "r", 0.5)
    set_if_present(uv_bias, "g", 0.5)
    shadow_uv = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, 40, 375
    )
    shadow_texture = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, 235, 360
    )
    set_if_present(shadow_texture, "parameter_name", "GrassShadowMask")
    default_shadow_texture = unreal.EditorAssetLibrary.load_asset("/Engine/EngineResources/DefaultTexture.DefaultTexture")
    if default_shadow_texture:
        set_if_present(shadow_texture, "texture", default_shadow_texture)
    shadow_mask = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, 430, 365
    )
    set_if_present(shadow_mask, "r", True)
    set_if_present(shadow_mask, "g", False)
    set_if_present(shadow_mask, "b", False)
    set_if_present(shadow_mask, "a", False)
    shadow_strength = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, 430, 465
    )
    set_if_present(shadow_strength, "parameter_name", "GrassShadowMaskStrength")
    set_if_present(shadow_strength, "default_value", 0.88)
    shadow_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 610, 420
    )
    shadow_tint = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, 165, 145
    )
    set_if_present(shadow_tint, "parameter_name", "GrassShadowMaskTint")
    set_if_present(shadow_tint, "default_value", unreal.LinearColor(0.16, 0.28, 0.12, 1.0))
    shadowed_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 430, 115
    )
    final_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 805, 130
    )
    distant_center = create_vector_parameter(
        material, "GrassDistantFadeCenter", unreal.LinearColor(0.0, 700.0, 0.0, 0.0), 1000, -265
    )
    distant_center_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, 1190, -265
    )
    set_if_present(distant_center_xy, "r", True)
    set_if_present(distant_center_xy, "g", True)
    set_if_present(distant_center_xy, "b", False)
    set_if_present(distant_center_xy, "a", False)
    distant_distance = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionDistance, 1390, -220
    )
    distant_start = create_scalar_parameter(material, "GrassDistantColorStartCm", 6400.0, 1190, -80)
    distant_inv_range = create_scalar_parameter(material, "GrassDistantColorInvRange", 1.0 / 7200.0, 1390, 25)
    distant_distance_offset = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 1585, -180
    )
    distant_distance_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1775, -180
    )
    distant_zero = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 1775, -35
    )
    distant_zero.set_editor_property("r", 0.0)
    distant_one = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 1965, -35
    )
    distant_one.set_editor_property("r", 1.0)
    distant_nonnegative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMax, 1965, -180
    )
    distant_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMin, 2155, -180
    )
    distant_color = create_vector_parameter(
        material, "GrassDistantColor", unreal.LinearColor(0.105, 0.245, 0.048, 1.0), 1965, 95
    )
    distant_final_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 2350, 25
    )
    distant_flatten_start = create_scalar_parameter(material, "GrassDistantFlattenStartCm", 10500.0, 2350, 220)
    distant_flatten_inv_range = create_scalar_parameter(material, "GrassDistantFlattenInvRange", 1.0 / 9500.0, 2550, 260)
    distant_flatten_cm = create_scalar_parameter(material, "GrassDistantFlattenCm", 78.0, 2550, 370)
    distant_flatten_offset = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 2750, 180
    )
    distant_flatten_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 2940, 180
    )
    distant_flatten_nonnegative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMax, 3130, 180
    )
    distant_flatten_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMin, 3320, 180
    )
    distant_flatten_height_mask = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 3510, 180
    )
    distant_flatten_amount = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 3700, 180
    )
    distant_flatten_neg_one = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 3700, 330
    )
    distant_flatten_neg_one.set_editor_property("r", -1.0)
    distant_flatten_negative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 3890, 180
    )
    distant_flatten_zero_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant2Vector, 3890, 330
    )
    set_if_present(distant_flatten_zero_xy, "r", 0.0)
    set_if_present(distant_flatten_zero_xy, "g", 0.0)
    distant_flatten_wpo = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAppendVector, 4080, 220
    )
    distant_combined_wpo = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, 4280, 820
    )
    distant_opacity_start = create_scalar_parameter(material, "GrassDistantOpacityStartCm", 15000.0, 2350, 515)
    distant_opacity_inv_range = create_scalar_parameter(material, "GrassDistantOpacityInvRange", 1.0 / 7000.0, 2550, 555)
    distant_opacity_offset = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 2750, 515
    )
    distant_opacity_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 2940, 515
    )
    distant_opacity_nonnegative = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMax, 3130, 515
    )
    distant_opacity_fade = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMin, 3320, 515
    )
    distant_opacity = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 3510, 515
    )
    tex_coord = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureCoordinate, -1140, -315
    )
    blade_v = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -940, -315
    )
    set_if_present(blade_v, "r", False)
    set_if_present(blade_v, "g", True)
    set_if_present(blade_v, "b", False)
    set_if_present(blade_v, "a", False)
    blade_mask = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -745, -315
    )
    wind_enabled = create_scalar_parameter(material, "GrassWindEnabled", 0.0, -1140, 650)
    wind_bend = create_scalar_parameter(material, "GrassWindBendCm", 18.0, -1140, 745)
    wind_lift = create_scalar_parameter(material, "GrassWindLiftCm", 0.0, -1140, 840)
    wind_world_frequency = create_scalar_parameter(material, "GrassWindWorldFrequency", 0.00115, -1140, 935)
    wind_patch_frequency = create_scalar_parameter(material, "GrassWindPatchFrequency", 0.00055, -1140, 1030)
    wind_speed = create_scalar_parameter(material, "GrassWindSpeed", 1.35, -1140, 1125)
    wind_gust = create_scalar_parameter(material, "GrassWindGustStrength", 1.0, -1140, 1220)
    wind_direction = create_vector_parameter(
        material, "GrassWindDirection", unreal.LinearColor(0.86, 0.50, 0.0, 0.0), -930, 650
    )
    wind_direction_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -720, 650
    )
    set_if_present(wind_direction_xy, "r", True)
    set_if_present(wind_direction_xy, "g", True)
    set_if_present(wind_direction_xy, "b", False)
    set_if_present(wind_direction_xy, "a", False)
    wind_patch_direction = create_vector_parameter(
        material, "GrassWindPatchDirection", unreal.LinearColor(-0.46, 0.89, 0.0, 0.0), -930, 760
    )
    wind_patch_direction_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -720, 760
    )
    set_if_present(wind_patch_direction_xy, "r", True)
    set_if_present(wind_patch_direction_xy, "g", True)
    set_if_present(wind_patch_direction_xy, "b", False)
    set_if_present(wind_patch_direction_xy, "a", False)
    wind_time = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTime, -720, 935
    )
    wind_main_dot = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionDotProduct, -520, 640
    )
    wind_main_spatial = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -335, 640
    )
    wind_main_time = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -335, 750
    )
    wind_main_phase = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, -145, 695
    )
    wind_main_wave = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSine, 45, 695
    )
    wind_patch_dot = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionDotProduct, -520, 850
    )
    wind_patch_spatial = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -335, 850
    )
    wind_patch_speed_scale = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -520, 1030
    )
    wind_patch_speed_scale.set_editor_property("r", 0.37)
    wind_patch_speed = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -335, 1010
    )
    wind_patch_time = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -145, 945
    )
    wind_patch_phase = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, 45, 900
    )
    wind_patch_wave = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSine, 230, 900
    )
    wind_half = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 45, 1060
    )
    wind_half.set_editor_property("r", 0.5)
    wind_main_half = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 230, 650
    )
    wind_main_01 = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, 415, 650
    )
    wind_patch_half = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 415, 890
    )
    wind_patch_01 = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, 600, 890
    )
    wind_gust_base = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 785, 760
    )
    wind_gust_amount = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 970, 760
    )
    wind_bend_signed = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 415, 520
    )
    wind_bend_gusted = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 600, 520
    )
    wind_bend_masked = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 785, 520
    )
    wind_bend_enabled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 970, 520
    )
    wind_xy_offset = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1160, 520
    )
    wind_lift_gusted = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1160, 760
    )
    wind_lift_masked = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1350, 760
    )
    wind_lift_enabled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1540, 760
    )
    wind_wpo = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAppendVector, 1740, 630
    )
    wind_texture_scale = create_scalar_parameter(material, "GrassWindTextureScale", 0.00018, -1140, 1340)
    wind_texture_speed = create_scalar_parameter(material, "GrassWindTextureSpeed", 0.030, -1140, 1435)
    wind_uv_base = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -520, 1240
    )
    wind_time_uv_speed = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -520, 1350
    )
    wind_uv_motion = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -335, 1320
    )
    wind_texture_uv = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, -145, 1265
    )
    wind_texture = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, 45, 1260
    )
    set_if_present(wind_texture, "parameter_name", "GrassWindTexture")
    if wind_texture_asset:
        set_if_present(wind_texture, "texture", wind_texture_asset)
    wind_texture_mask = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, 230, 1265
    )
    set_if_present(wind_texture_mask, "r", True)
    set_if_present(wind_texture_mask, "g", False)
    set_if_present(wind_texture_mask, "b", False)
    set_if_present(wind_texture_mask, "a", False)
    wind_texture_center = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 230, 1385
    )
    wind_texture_center.set_editor_property("r", 0.5)
    wind_texture_centered = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 415, 1265
    )
    wind_texture_double = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 415, 1385
    )
    wind_texture_double.set_editor_property("r", 2.0)
    wind_texture_signed = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 600, 1265
    )
    wind_texture_bend = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 785, 1265
    )
    wind_texture_bend_gust = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 970, 1265
    )
    wind_texture_bend_masked = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1160, 1265
    )
    wind_texture_bend_enabled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1350, 1265
    )
    wind_texture_xy_offset = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1540, 1265
    )
    wind_texture_lift = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 600, 1490
    )
    wind_texture_lift_gust = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 785, 1490
    )
    wind_texture_lift_masked = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 970, 1490
    )
    wind_texture_lift_enabled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1160, 1490
    )
    wind_texture_wpo = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAppendVector, 1740, 1365
    )
    wind_tri_frac = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionFrac, 230, 1650
    )
    wind_patch_tri_frac = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionFrac, 230, 1860
    )
    wind_tri_double_const = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 230, 2070
    )
    wind_tri_double_const.set_editor_property("r", 2.0)
    wind_tri_one_const = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 230, 2160
    )
    wind_tri_one_const.set_editor_property("r", 1.0)
    wind_tri_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 415, 1650
    )
    wind_patch_tri_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 415, 1860
    )
    wind_tri_centered = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 600, 1650
    )
    wind_patch_tri_centered = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 600, 1860
    )
    wind_tri_abs = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAbs, 785, 1650
    )
    wind_patch_tri_abs = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAbs, 785, 1860
    )
    wind_tri_main = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 970, 1650
    )
    wind_tri_patch = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 970, 1860
    )
    wind_tri_gust_raw = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1160, 1750
    )
    wind_tri_gust = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1350, 1750
    )
    wind_tri_bend = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1540, 1650
    )
    wind_tri_bend_masked = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1730, 1650
    )
    wind_tri_bend_enabled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1920, 1650
    )
    wind_tri_xy_offset = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 2110, 1650
    )
    wind_tri_lift = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1540, 1920
    )
    wind_tri_lift_masked = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1730, 1920
    )
    wind_tri_lift_enabled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1920, 1920
    )
    wind_tri_wpo = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAppendVector, 2300, 1780
    )
    object_position_class = getattr(unreal, "MaterialExpressionObjectPositionWS", unreal.MaterialExpressionWorldPosition)
    wind_simple_object_position = unreal.MaterialEditingLibrary.create_material_expression(
        material, object_position_class, -1140, 2260
    )
    wind_simple_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -940, 2260
    )
    set_if_present(wind_simple_xy, "r", True)
    set_if_present(wind_simple_xy, "g", True)
    set_if_present(wind_simple_xy, "b", False)
    set_if_present(wind_simple_xy, "a", False)
    wind_simple_dot = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionDotProduct, -735, 2260
    )
    wind_simple_spatial = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -540, 2260
    )
    wind_simple_time = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -540, 2375
    )
    wind_simple_phase = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, -340, 2315
    )
    wind_simple_frac = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionFrac, -145, 2315
    )
    wind_simple_double = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -145, 2435
    )
    wind_simple_double.set_editor_property("r", 2.0)
    wind_simple_one = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -145, 2525
    )
    wind_simple_one.set_editor_property("r", 1.0)
    wind_simple_scaled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 45, 2315
    )
    wind_simple_centered = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 235, 2315
    )
    wind_simple_abs = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAbs, 425, 2315
    )
    wind_simple_tri = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 615, 2315
    )
    wind_simple_gust = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 805, 2315
    )
    wind_simple_bend = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 995, 2255
    )
    wind_simple_bend_masked = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1185, 2255
    )
    wind_simple_bend_enabled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1375, 2255
    )
    wind_simple_xy_offset = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1565, 2255
    )
    wind_simple_lift = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 995, 2465
    )
    wind_simple_lift_masked = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1185, 2465
    )
    wind_simple_lift_enabled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1375, 2465
    )
    wind_simple_wpo = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAppendVector, 1755, 2355
    )
    blood_mask, _blood_core = create_blood_mask_sample(material, world_xy, 2550, -475)
    blood_grass_strength = create_scalar_parameter(material, "BloodGrassStrength", 0.0, 2750, -590)
    blood_base_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 2940, -555
    )
    blood_tip_reduce = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 2750, -355
    )
    blood_tip_reduce.set_editor_property("r", 0.55)
    blood_tip_amount = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 2940, -385
    )
    blood_one = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, 2940, -270
    )
    blood_one.set_editor_property("r", 1.0)
    blood_blade_factor = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSubtract, 3130, -355
    )
    blood_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 3320, -475
    )
    blood_grass_color = create_vector_parameter(
        material, "BloodGrassColor", unreal.LinearColor(0.155, 0.006, 0.004, 1.0), 3320, -615
    )
    blood_grass_final = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 3510, -535
    )

    unreal.MaterialEditingLibrary.connect_material_expressions(
        dark_color, "", color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        light_color, "", color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        random, "", color, "Alpha"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        root_color, "", grass_gradient, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        tip_color, "", grass_gradient, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_mask, "", grass_gradient, "Alpha"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        grass_gradient, "", blade_color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        color, "", blade_color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_position, "", world_xy, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_center, "", shadow_center_xy, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_xy, "", shadow_relative, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_center_xy, "", shadow_relative, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_relative, "", shadow_scaled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_inv_extent, "", shadow_scaled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_scaled, "", shadow_uv, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        uv_bias, "", shadow_uv, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_uv, "", shadow_texture, "UVs"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_texture, "", shadow_mask, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_mask, "", shadow_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_strength, "", shadow_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_color, "", shadowed_color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_tint, "", shadowed_color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_color, "", final_color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadowed_color, "", final_color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        shadow_alpha, "", final_color, "Alpha"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_center, "", distant_center_xy, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_xy, "", distant_distance, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_center_xy, "", distant_distance, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_distance, "", distant_distance_offset, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_start, "", distant_distance_offset, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_distance_offset, "", distant_distance_scaled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_inv_range, "", distant_distance_scaled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_distance_scaled, "", distant_nonnegative, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_zero, "", distant_nonnegative, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_nonnegative, "", distant_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_one, "", distant_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        final_color, "", distant_final_color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_color, "", distant_final_color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_alpha, "", distant_final_color, "Alpha"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_distance, "", distant_flatten_offset, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_start, "", distant_flatten_offset, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_offset, "", distant_flatten_scaled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_inv_range, "", distant_flatten_scaled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_scaled, "", distant_flatten_nonnegative, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_zero, "", distant_flatten_nonnegative, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_nonnegative, "", distant_flatten_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_one, "", distant_flatten_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_alpha, "", distant_flatten_height_mask, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_mask, "", distant_flatten_height_mask, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_height_mask, "", distant_flatten_amount, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_cm, "", distant_flatten_amount, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_amount, "", distant_flatten_negative, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_neg_one, "", distant_flatten_negative, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_zero_xy, "", distant_flatten_wpo, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_negative, "", distant_flatten_wpo, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_mask, "", blood_base_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_grass_strength, "", blood_base_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_v, "", blood_tip_amount, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_tip_reduce, "", blood_tip_amount, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_one, "", blood_blade_factor, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_tip_amount, "", blood_blade_factor, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_base_alpha, "", blood_alpha, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_blade_factor, "", blood_alpha, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_final_color, "", blood_grass_final, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_grass_color, "", blood_grass_final, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blood_alpha, "", blood_grass_final, "Alpha"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_distance, "", distant_opacity_offset, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_opacity_start, "", distant_opacity_offset, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_opacity_offset, "", distant_opacity_scaled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_opacity_inv_range, "", distant_opacity_scaled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_opacity_scaled, "", distant_opacity_nonnegative, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_zero, "", distant_opacity_nonnegative, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_opacity_nonnegative, "", distant_opacity_fade, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_one, "", distant_opacity_fade, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_one, "", distant_opacity, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_opacity_fade, "", distant_opacity, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        tex_coord, "", blade_v, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_v, "", blade_mask, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_v, "", blade_mask, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_direction, "", wind_direction_xy, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_direction, "", wind_patch_direction_xy, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_xy, "", wind_main_dot, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_direction_xy, "", wind_main_dot, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_main_dot, "", wind_main_spatial, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_world_frequency, "", wind_main_spatial, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_time, "", wind_main_time, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_speed, "", wind_main_time, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_main_spatial, "", wind_main_phase, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_main_time, "", wind_main_phase, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_main_phase, "", wind_main_wave, ""
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_xy, "", wind_patch_dot, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_direction_xy, "", wind_patch_dot, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_dot, "", wind_patch_spatial, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_frequency, "", wind_patch_spatial, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_speed, "", wind_patch_speed, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_speed_scale, "", wind_patch_speed, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_time, "", wind_patch_time, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_speed, "", wind_patch_time, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_spatial, "", wind_patch_phase, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_time, "", wind_patch_phase, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_phase, "", wind_patch_wave, ""
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_main_wave, "", wind_main_half, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_half, "", wind_main_half, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_main_half, "", wind_main_01, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_half, "", wind_main_01, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_wave, "", wind_patch_half, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_half, "", wind_patch_half, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_half, "", wind_patch_01, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_half, "", wind_patch_01, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_main_01, "", wind_gust_base, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_01, "", wind_gust_base, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_gust_base, "", wind_gust_amount, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_gust, "", wind_gust_amount, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_main_wave, "", wind_bend_signed, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_bend, "", wind_bend_signed, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_bend_signed, "", wind_bend_gusted, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_gust_amount, "", wind_bend_gusted, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_bend_gusted, "", wind_bend_masked, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_mask, "", wind_bend_masked, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_bend_masked, "", wind_bend_enabled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_enabled, "", wind_bend_enabled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_direction_xy, "", wind_xy_offset, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_bend_enabled, "", wind_xy_offset, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_gust_amount, "", wind_lift_gusted, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_lift, "", wind_lift_gusted, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_lift_gusted, "", wind_lift_masked, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_mask, "", wind_lift_masked, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_lift_masked, "", wind_lift_enabled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_enabled, "", wind_lift_enabled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_xy_offset, "", wind_wpo, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_lift_enabled, "", wind_wpo, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_xy, "", wind_uv_base, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_scale, "", wind_uv_base, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_time, "", wind_time_uv_speed, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_speed, "", wind_time_uv_speed, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_direction_xy, "", wind_uv_motion, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_time_uv_speed, "", wind_uv_motion, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_uv_base, "", wind_texture_uv, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_uv_motion, "", wind_texture_uv, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_uv, "", wind_texture, "UVs"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture, "", wind_texture_mask, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_mask, "", wind_texture_centered, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_center, "", wind_texture_centered, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_centered, "", wind_texture_signed, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_double, "", wind_texture_signed, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_signed, "", wind_texture_bend, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_bend, "", wind_texture_bend, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_bend, "", wind_texture_bend_gust, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_gust, "", wind_texture_bend_gust, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_bend_gust, "", wind_texture_bend_masked, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_mask, "", wind_texture_bend_masked, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_bend_masked, "", wind_texture_bend_enabled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_enabled, "", wind_texture_bend_enabled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_direction_xy, "", wind_texture_xy_offset, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_bend_enabled, "", wind_texture_xy_offset, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_mask, "", wind_texture_lift, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_lift, "", wind_texture_lift, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_lift, "", wind_texture_lift_gust, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_gust, "", wind_texture_lift_gust, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_lift_gust, "", wind_texture_lift_masked, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_mask, "", wind_texture_lift_masked, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_lift_masked, "", wind_texture_lift_enabled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_enabled, "", wind_texture_lift_enabled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_xy_offset, "", wind_texture_wpo, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_texture_lift_enabled, "", wind_texture_wpo, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_main_phase, "", wind_tri_frac, ""
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_phase, "", wind_patch_tri_frac, ""
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_frac, "", wind_tri_scaled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_double_const, "", wind_tri_scaled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_tri_frac, "", wind_patch_tri_scaled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_double_const, "", wind_patch_tri_scaled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_scaled, "", wind_tri_centered, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_one_const, "", wind_tri_centered, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_tri_scaled, "", wind_patch_tri_centered, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_one_const, "", wind_patch_tri_centered, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_centered, "", wind_tri_abs, ""
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_tri_centered, "", wind_patch_tri_abs, ""
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_one_const, "", wind_tri_main, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_abs, "", wind_tri_main, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_one_const, "", wind_tri_patch, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_patch_tri_abs, "", wind_tri_patch, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_main, "", wind_tri_gust_raw, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_patch, "", wind_tri_gust_raw, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_gust_raw, "", wind_tri_gust, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_gust, "", wind_tri_gust, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_gust, "", wind_tri_bend, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_bend, "", wind_tri_bend, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_bend, "", wind_tri_bend_masked, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_mask, "", wind_tri_bend_masked, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_bend_masked, "", wind_tri_bend_enabled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_enabled, "", wind_tri_bend_enabled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_direction_xy, "", wind_tri_xy_offset, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_bend_enabled, "", wind_tri_xy_offset, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_gust, "", wind_tri_lift, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_lift, "", wind_tri_lift, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_lift, "", wind_tri_lift_masked, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_mask, "", wind_tri_lift_masked, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_lift_masked, "", wind_tri_lift_enabled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_enabled, "", wind_tri_lift_enabled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_xy_offset, "", wind_tri_wpo, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_tri_lift_enabled, "", wind_tri_wpo, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_object_position, "", wind_simple_xy, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_xy, "", wind_simple_dot, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_direction_xy, "", wind_simple_dot, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_dot, "", wind_simple_spatial, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_world_frequency, "", wind_simple_spatial, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_time, "", wind_simple_time, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_speed, "", wind_simple_time, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_spatial, "", wind_simple_phase, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_time, "", wind_simple_phase, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_phase, "", wind_simple_frac, ""
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_frac, "", wind_simple_scaled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_double, "", wind_simple_scaled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_scaled, "", wind_simple_centered, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_one, "", wind_simple_centered, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_centered, "", wind_simple_abs, ""
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_one, "", wind_simple_tri, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_abs, "", wind_simple_tri, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_tri, "", wind_simple_gust, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_gust, "", wind_simple_gust, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_gust, "", wind_simple_bend, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_bend, "", wind_simple_bend, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_bend, "", wind_simple_bend_masked, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_mask, "", wind_simple_bend_masked, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_bend_masked, "", wind_simple_bend_enabled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_enabled, "", wind_simple_bend_enabled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_direction_xy, "", wind_simple_xy_offset, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_bend_enabled, "", wind_simple_xy_offset, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_gust, "", wind_simple_lift, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_lift, "", wind_simple_lift, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_lift, "", wind_simple_lift_masked, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        blade_mask, "", wind_simple_lift_masked, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_lift_masked, "", wind_simple_lift_enabled, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_enabled, "", wind_simple_lift_enabled, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_xy_offset, "", wind_simple_wpo, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_lift_enabled, "", wind_simple_wpo, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        wind_simple_wpo, "", distant_combined_wpo, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        distant_flatten_wpo, "", distant_combined_wpo, "B"
    )

    unreal.MaterialEditingLibrary.connect_material_property(
        blood_grass_final, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        blood_grass_final, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        distant_combined_wpo, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        distant_opacity, "", unreal.MaterialProperty.MP_OPACITY_MASK
    )
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def rebuild_tree_vertex_wind_material():
    material = get_or_create_material("M_ProphecyTreeVertexWind")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)

    set_if_present(material, "two_sided", True)
    set_if_present(material, "used_with_instanced_static_meshes", True)
    set_if_present(material, "b_used_with_instanced_static_meshes", True)
    set_if_present(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_if_present(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    set_if_present(material, "is_sky", False)
    set_if_present(material, "b_is_sky", False)
    try:
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    except Exception:
        pass
    try:
        usage = unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES
        unreal.MaterialEditingLibrary.set_material_usage(material, usage)
    except Exception:
        pass

    vertex_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVertexColor, -1260, -120
    )
    dark_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -1260, -280
    )
    dark_color.set_editor_property("constant", unreal.LinearColor(0.060, 0.155, 0.035, 1.0))
    light_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -1260, -180
    )
    light_color.set_editor_property("constant", unreal.LinearColor(0.145, 0.285, 0.075, 1.0))
    random = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionPerInstanceRandom, -1260, -70
    )
    color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, -1040, -215
    )
    emissive_scale = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -1040, -20
    )
    emissive_scale.set_editor_property("r", 0.74)
    emissive = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -840, -70
    )
    roughness = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -840, 90
    )
    roughness.set_editor_property("r", 0.95)
    specular = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -840, 180
    )
    specular.set_editor_property("r", 0.03)

    object_position_class = getattr(unreal, "MaterialExpressionObjectPositionWS", unreal.MaterialExpressionWorldPosition)
    object_position = unreal.MaterialEditingLibrary.create_material_expression(
        material, object_position_class, -1260, 275
    )
    object_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -1040, 275
    )
    set_if_present(object_xy, "r", True)
    set_if_present(object_xy, "g", True)
    set_if_present(object_xy, "b", False)
    set_if_present(object_xy, "a", False)
    wind_direction = create_vector_parameter(
        material, "TreeWindDirection", unreal.LinearColor(0.86, 0.50, 0.0, 0.0), -1260, 405
    )
    wind_direction_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -1040, 405
    )
    set_if_present(wind_direction_xy, "r", True)
    set_if_present(wind_direction_xy, "g", True)
    set_if_present(wind_direction_xy, "b", False)
    set_if_present(wind_direction_xy, "a", False)
    wind_enabled = create_scalar_parameter(material, "TreeWindEnabled", 0.0, -1260, 540)
    wind_bend = create_scalar_parameter(material, "TreeWindBendCm", 30.0, -1260, 635)
    wind_lift = create_scalar_parameter(material, "TreeWindLiftCm", 0.0, -1260, 730)
    wind_world_frequency = create_scalar_parameter(material, "TreeWindWorldFrequency", 0.00034, -1260, 825)
    wind_speed = create_scalar_parameter(material, "TreeWindSpeed", 0.60, -1260, 920)
    wind_gust = create_scalar_parameter(material, "TreeWindGustStrength", 0.55, -1260, 1015)
    wind_time = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTime, -1040, 920
    )
    wind_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -1040, 525
    )
    set_if_present(wind_alpha, "r", False)
    set_if_present(wind_alpha, "g", False)
    set_if_present(wind_alpha, "b", False)
    set_if_present(wind_alpha, "a", True)

    wind_dot = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionDotProduct, -830, 275
    )
    wind_spatial = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -635, 275
    )
    wind_time_speed = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -635, 905
    )
    wind_phase = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, -430, 370
    )
    wind_wave = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSine, -225, 370
    )
    wind_half = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -225, 500
    )
    wind_half.set_editor_property("r", 0.5)
    wind_wave_half = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -20, 370
    )
    wind_wave_01 = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAdd, 185, 370
    )
    wind_gusted_01 = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 390, 370
    )
    wind_signed_bend = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -20, 610
    )
    wind_bend_gusted = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 185, 610
    )
    wind_bend_weighted = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 390, 610
    )
    wind_bend_enabled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 595, 610
    )
    wind_xy_offset = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 800, 610
    )
    wind_lift_gusted = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 595, 385
    )
    wind_lift_weighted = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 800, 385
    )
    wind_lift_enabled = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 1005, 385
    )
    wind_wpo = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionAppendVector, 1210, 515
    )

    unreal.MaterialEditingLibrary.connect_material_expressions(vertex_color, "", emissive, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(emissive_scale, "", emissive, "B")
    unreal.MaterialEditingLibrary.connect_material_property(vertex_color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
    unreal.MaterialEditingLibrary.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)

    unreal.MaterialEditingLibrary.connect_material_expressions(object_position, "", object_xy, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_direction, "", wind_direction_xy, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(object_xy, "", wind_dot, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_direction_xy, "", wind_dot, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_dot, "", wind_spatial, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_world_frequency, "", wind_spatial, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_time, "", wind_time_speed, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_speed, "", wind_time_speed, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_spatial, "", wind_phase, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_time_speed, "", wind_phase, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_phase, "", wind_wave, "")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_wave, "", wind_wave_half, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_half, "", wind_wave_half, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_wave_half, "", wind_wave_01, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_half, "", wind_wave_01, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_wave_01, "", wind_gusted_01, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_gust, "", wind_gusted_01, "B")

    unreal.MaterialEditingLibrary.connect_material_expressions(wind_wave, "", wind_signed_bend, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_bend, "", wind_signed_bend, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_signed_bend, "", wind_bend_gusted, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_gust, "", wind_bend_gusted, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_bend_gusted, "", wind_bend_weighted, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(vertex_color, "A", wind_bend_weighted, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_bend_weighted, "", wind_bend_enabled, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_enabled, "", wind_bend_enabled, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_direction_xy, "", wind_xy_offset, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_bend_enabled, "", wind_xy_offset, "B")

    unreal.MaterialEditingLibrary.connect_material_expressions(wind_gusted_01, "", wind_lift_gusted, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_lift, "", wind_lift_gusted, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_lift_gusted, "", wind_lift_weighted, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(vertex_color, "A", wind_lift_weighted, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_lift_weighted, "", wind_lift_enabled, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_enabled, "", wind_lift_enabled, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_xy_offset, "", wind_wpo, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(wind_lift_enabled, "", wind_wpo, "B")
    # Playable-area trees are static for now; shadows are baked into receiver masks, so keep the tree shader cheap.

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def rebuild_far_hills_material():
    material = get_or_create_material("M_ProphecyGrassFarHills")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    noise_texture_asset = import_ground_texture()

    set_if_present(material, "two_sided", False)
    set_if_present(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_if_present(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    set_if_present(material, "is_sky", False)
    set_if_present(material, "b_is_sky", False)
    set_if_present(material, "use_translucency_vertex_fog", False)
    set_if_present(material, "b_use_translucency_vertex_fog", False)
    set_if_present(material, "apply_cloud_fogging", False)
    set_if_present(material, "b_apply_cloud_fogging", False)
    try:
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    except Exception:
        pass

    dark_color = create_vector_parameter(material, "GrassDarkColor", GRASS_FAR_HILLS_DARK, -980, -170)
    light_color = create_vector_parameter(material, "GrassLightColor", GRASS_FAR_HILLS_LIGHT, -980, -60)
    world_position = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionWorldPosition, -980, 80
    )
    world_xy = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -780, 80
    )
    set_if_present(world_xy, "r", True)
    set_if_present(world_xy, "g", True)
    set_if_present(world_xy, "b", False)
    set_if_present(world_xy, "a", False)
    noise_scale = create_scalar_parameter(material, "FarGrassNoiseScale", 1.0 / 26000.0, -780, 215)
    noise_uv = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -570, 120
    )
    noise_texture = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, -360, 105
    )
    set_if_present(noise_texture, "parameter_name", "FarGrassNoiseTexture")
    if noise_texture_asset:
        set_if_present(noise_texture, "texture", noise_texture_asset)
    noise_mask = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionComponentMask, -145, 110
    )
    set_if_present(noise_mask, "r", True)
    set_if_present(noise_mask, "g", False)
    set_if_present(noise_mask, "b", False)
    set_if_present(noise_mask, "a", False)
    color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 85, -80
    )

    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_position, "", world_xy, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        world_xy, "", noise_uv, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        noise_scale, "", noise_uv, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        noise_uv, "", noise_texture, "UVs"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        noise_texture, "", noise_mask, "None"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        dark_color, "", color, "A"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        light_color, "", color, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(
        noise_mask, "", color, "Alpha"
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        color, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def rebuild_grass_contact_shadow_material():
    material = get_or_create_material("M_ProphecyGrassContactShadow")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)

    set_if_present(material, "two_sided", True)
    set_if_present(material, "used_with_instanced_static_meshes", True)
    set_if_present(material, "b_used_with_instanced_static_meshes", True)
    set_if_present(material, "blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    set_if_present(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    try:
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    except Exception:
        pass
    try:
        usage = unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES
        unreal.MaterialEditingLibrary.set_material_usage(material, usage)
    except Exception:
        pass

    vertex_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVertexColor, -260, -40
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        vertex_color, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        vertex_color, "RGB", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        vertex_color, "A", unreal.MaterialProperty.MP_OPACITY
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


ensure_dir(ASSET_DIR)
grass = rebuild_grass_material()
ground = rebuild_ground_material()
sky = unreal.EditorAssetLibrary.load_asset(f"{ASSET_DIR}/M_ProphecySky_Unlit")
terrain = rebuild_shared_terrain_material()
field_grass = rebuild_field_grass_material()
tree_wind = rebuild_tree_vertex_wind_material()
far_hills = rebuild_far_hills_material()
contact_shadow = rebuild_grass_contact_shadow_material()
print(f"PROPHECY_GRASS_MATERIAL {grass.get_path_name()}")
print(f"PROPHECY_GROUND_MATERIAL {ground.get_path_name()}")
if sky:
    print(f"PROPHECY_SKY_MATERIAL {sky.get_path_name()}")
print(f"PROPHECY_TERRAIN_SHARED_MATERIAL {terrain.get_path_name()}")
print(f"PROPHECY_FIELD_GRASS_MATERIAL {field_grass.get_path_name()}")
print(f"PROPHECY_TREE_VERTEX_WIND_MATERIAL {tree_wind.get_path_name()}")
print(f"PROPHECY_FAR_HILLS_MATERIAL {far_hills.get_path_name()}")
print(f"PROPHECY_GRASS_CONTACT_SHADOW_MATERIAL {contact_shadow.get_path_name()}")
