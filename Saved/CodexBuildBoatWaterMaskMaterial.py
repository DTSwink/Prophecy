import datetime
import json
import math
import os

import unreal


MATERIAL_PATH = "/Game/_mygame/assets/boat/StaticMeshes/NewMaterial"
TEXTURE_PATH = "/Game/_mygame/assets/boat/StaticMeshes/Generated/T_BoatInside_WaterMask"
TEXTURE_SOURCE = os.path.join(
    unreal.Paths.project_saved_dir(),
    "CodexGenerated",
    "BoatWaterMask",
    "T_BoatInside_WaterMask.png",
)
METADATA_SOURCE = os.path.join(
    unreal.Paths.project_saved_dir(),
    "CodexGenerated",
    "BoatWaterMask",
    "T_BoatInside_WaterMask.json",
)

with open(METADATA_SOURCE, "r", encoding="utf-8") as metadata_file:
    metadata = json.load(metadata_file)

material = unreal.EditorAssetLibrary.load_asset(MATERIAL_PATH)
if not material:
    raise RuntimeError("Missing material: " + MATERIAL_PATH)
if material.get_editor_property("blend_mode") != unreal.BlendMode.BLEND_MASKED:
    raise RuntimeError("NewMaterial is no longer Masked; refusing to change it")

editing = unreal.MaterialEditingLibrary
expression_count = editing.get_num_material_expressions(material)
if expression_count != 0:
    raise RuntimeError(
        "NewMaterial now contains {} expressions; refusing to overwrite the user's graph".format(
            expression_count
        )
    )

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = (
    "/Game/_mygame/assets/boat/StaticMeshes/_CodexBackups/"
    "NewMaterial_PreBoatMask_" + timestamp
)
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
backup = asset_tools.duplicate_asset(
    backup_path.rsplit("/", 1)[1], backup_path.rsplit("/", 1)[0], material
)
if not backup or not unreal.EditorAssetLibrary.save_asset(
    backup_path, only_if_is_dirty=False
):
    raise RuntimeError("Could not create a recoverable NewMaterial backup")

task = unreal.AssetImportTask()
task.set_editor_property("filename", TEXTURE_SOURCE)
task.set_editor_property(
    "destination_path", "/Game/_mygame/assets/boat/StaticMeshes/Generated"
)
task.set_editor_property("destination_name", "T_BoatInside_WaterMask")
task.set_editor_property("automated", True)
task.set_editor_property("replace_existing", True)
task.set_editor_property("save", True)
asset_tools.import_asset_tasks([task])

texture = unreal.EditorAssetLibrary.load_asset(TEXTURE_PATH)
if not texture:
    raise RuntimeError("Failed to import the generated boat mask texture")
texture.set_editor_property("srgb", False)
texture.set_editor_property(
    "compression_settings", unreal.TextureCompressionSettings.TC_MASKS
)
texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
texture.set_editor_property("filter", unreal.TextureFilter.TF_BILINEAR)
if hasattr(texture, "post_edit_change"):
    texture.post_edit_change()
unreal.EditorAssetLibrary.save_asset(TEXTURE_PATH, only_if_is_dirty=False)

def set_optional(obj, property_name, value):
    try:
        obj.set_editor_property(property_name, value)
    except Exception:
        pass

def make(expression_class, x, y, description=""):
    expression = editing.create_material_expression(material, expression_class, x, y)
    if not expression:
        raise RuntimeError("Failed to create " + expression_class.__name__)
    if description:
        set_optional(expression, "desc", description)
    return expression

def connect(source, source_output, target, target_input, label):
    if not editing.connect_material_expressions(
        source, source_output, target, target_input
    ):
        raise RuntimeError("Failed material connection: " + label)

def vector_parameter(name, value, x, y, description):
    expression = make(
        unreal.MaterialExpressionVectorParameter, x, y, description
    )
    expression.set_editor_property("parameter_name", unreal.Name(name))
    expression.set_editor_property("default_value", unreal.LinearColor(*value))
    set_optional(expression, "group", unreal.Name("Boat Water Mask"))
    return expression

def component_mask(source, channels, x, y, description):
    expression = make(unreal.MaterialExpressionComponentMask, x, y, description)
    expression.set_editor_property("r", "R" in channels)
    expression.set_editor_property("g", "G" in channels)
    expression.set_editor_property("b", "B" in channels)
    expression.set_editor_property("a", "A" in channels)
    connect(source, "", expression, "", description)
    return expression

def rotate_axis(quaternion, axis):
    qx, qy, qz, qw = quaternion
    vx, vy, vz = axis
    tx = 2.0 * (qy * vz - qz * vy)
    ty = 2.0 * (qz * vx - qx * vz)
    tz = 2.0 * (qx * vy - qy * vx)
    return (
        vx + qw * tx + (qy * tz - qz * ty),
        vy + qw * ty + (qz * tx - qx * tz),
        vz + qw * tz + (qx * ty - qy * tx),
    )

inside_transform = metadata["inside_actor"]
origin = inside_transform["location"]
rotation = inside_transform["rotation"]
scale = inside_transform["scale"]
axis_x = rotate_axis(rotation, (1.0, 0.0, 0.0))
axis_y = rotate_axis(rotation, (0.0, 1.0, 0.0))
axis_x = tuple(value / scale[0] for value in axis_x)
axis_y = tuple(value / scale[1] for value in axis_y)

created = []
try:
    world_position = make(
        unreal.MaterialExpressionWorldPosition,
        -1500,
        0,
        "Current water pixel in absolute world space",
    )
    origin_parameter = vector_parameter(
        "BoatMask_Origin",
        (origin[0], origin[1], origin[2], 0.0),
        -1500,
        -360,
        "World origin of the SM_Boat_Inside test actor",
    )
    origin_rgb = component_mask(
        origin_parameter, "RGB", -1250, -360, "Boat origin RGB"
    )
    offset = make(
        unreal.MaterialExpressionSubtract,
        -1040,
        0,
        "World position relative to the blockout",
    )
    connect(world_position, "", offset, "A", "WorldPosition -> Offset A")
    connect(origin_rgb, "", offset, "B", "Origin -> Offset B")

    axis_x_parameter = vector_parameter(
        "BoatMask_WorldToLocalX",
        (axis_x[0], axis_x[1], axis_x[2], 0.0),
        -1040,
        -430,
        "World-space local-X basis divided by component scale",
    )
    axis_y_parameter = vector_parameter(
        "BoatMask_WorldToLocalY",
        (axis_y[0], axis_y[1], axis_y[2], 0.0),
        -1040,
        430,
        "World-space local-Y basis divided by component scale",
    )
    axis_x_rgb = component_mask(
        axis_x_parameter, "RGB", -790, -430, "World-to-local X RGB"
    )
    axis_y_rgb = component_mask(
        axis_y_parameter, "RGB", -790, 430, "World-to-local Y RGB"
    )

    local_x = make(
        unreal.MaterialExpressionDotProduct, -570, -160, "Blockout local X"
    )
    local_y = make(
        unreal.MaterialExpressionDotProduct, -570, 160, "Blockout local Y"
    )
    connect(offset, "", local_x, "A", "Offset -> LocalX A")
    connect(axis_x_rgb, "", local_x, "B", "AxisX -> LocalX B")
    connect(offset, "", local_y, "A", "Offset -> LocalY A")
    connect(axis_y_rgb, "", local_y, "B", "AxisY -> LocalY B")

    local_xy = make(
        unreal.MaterialExpressionAppendVector, -340, 0, "Blockout local XY"
    )
    connect(local_x, "", local_xy, "A", "LocalX -> Append A")
    connect(local_y, "", local_xy, "B", "LocalY -> Append B")

    local_min = metadata["local_min"]
    inv_size = metadata["local_inv_size"]
    min_parameter = vector_parameter(
        "BoatMask_LocalMin",
        (local_min[0], local_min[1], 0.0, 0.0),
        -340,
        -380,
        "Padded local XY minimum used when the texture was baked",
    )
    inv_size_parameter = vector_parameter(
        "BoatMask_InvSize",
        (inv_size[0], inv_size[1], 0.0, 0.0),
        140,
        -380,
        "Inverse padded local XY dimensions",
    )
    min_rg = component_mask(min_parameter, "RG", -100, -380, "Local minimum RG")
    inv_rg = component_mask(
        inv_size_parameter, "RG", 380, -380, "Inverse dimensions RG"
    )

    uv_offset = make(
        unreal.MaterialExpressionSubtract, -80, 0, "Local XY minus mask minimum"
    )
    connect(local_xy, "", uv_offset, "A", "LocalXY -> UV offset A")
    connect(min_rg, "", uv_offset, "B", "LocalMin -> UV offset B")
    uv = make(
        unreal.MaterialExpressionMultiply, 180, 0, "Blockout-local mask UV"
    )
    connect(uv_offset, "", uv, "A", "UV offset -> UV A")
    connect(inv_rg, "", uv, "B", "InvSize -> UV B")

    texture_sample = make(
        unreal.MaterialExpressionTextureSampleParameter2D,
        460,
        0,
        "Baked projected silhouette of SM_Boat_Inside",
    )
    texture_sample.set_editor_property(
        "parameter_name", unreal.Name("BoatMask_Texture")
    )
    texture_sample.set_editor_property("texture", texture)
    texture_sample.set_editor_property(
        "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS
    )
    set_optional(texture_sample, "group", unreal.Name("Boat Water Mask"))
    # UE 5.7's Python material editor names the texture coordinate pin "UVs".
    connect(uv, "", texture_sample, "UVs", "UV -> Texture Coordinates")

    invert = make(
        unreal.MaterialExpressionOneMinus,
        760,
        0,
        "One outside the boat footprint, zero inside",
    )
    connect(texture_sample, "R", invert, "", "Mask R -> OneMinus")
    if not editing.connect_material_property(
        invert, "", unreal.MaterialProperty.MP_OPACITY_MASK
    ):
        raise RuntimeError("Failed to connect the generated mask to Opacity Mask")

    if hasattr(material, "post_edit_change"):
        material.post_edit_change()
    compile_errors = []
    if hasattr(editing, "recompile_material"):
        compile_result = editing.recompile_material(material)
        compile_errors = list(compile_result) if compile_result else []
    if compile_errors:
        raise RuntimeError("Material compile errors: " + " | ".join(compile_errors))
    if not unreal.EditorAssetLibrary.save_asset(
        MATERIAL_PATH, only_if_is_dirty=False
    ):
        raise RuntimeError("Failed to save NewMaterial")

    print(
        json.dumps(
            {
                "material": MATERIAL_PATH,
                "texture": TEXTURE_PATH,
                "backup": backup_path,
                "expression_count": editing.get_num_material_expressions(material),
                "compile_errors": compile_errors,
                "mask_origin": origin,
                "mask_local_min": local_min,
                "mask_inv_size": inv_size,
            },
            indent=2,
        )
    )
except Exception:
    # NewMaterial was empty before this script. Restore that exact state if
    # any node creation, connection, compile, or save step fails.
    # UE 5.7 removes only one expression layer per call when nodes reference
    # each other, so repeat until the graph is actually empty.
    for _ in range(32):
        if editing.get_num_material_expressions(material) == 0:
            break
        editing.delete_all_material_expressions(material)
    if hasattr(material, "post_edit_change"):
        material.post_edit_change()
    unreal.EditorAssetLibrary.save_asset(MATERIAL_PATH, only_if_is_dirty=False)
    raise
