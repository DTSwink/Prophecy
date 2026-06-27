import traceback

import unreal


ASSET_DIR = "/Game/Prophecy/BloodTexturePainting"
MF_PATH = f"{ASSET_DIR}/MF_BloodPaintMaskBlend"
MF_SURFACE_PATH = f"{ASSET_DIR}/MF_BloodPaintSurface"
CLEAN_TEST_PATH = f"{ASSET_DIR}/M_Test_BloodMaskBlend_Clean"
FULL_TEST_PATH = f"{ASSET_DIR}/M_Test_BloodMaskBlend_FullBlood"
BRUSH_PATH = f"{ASSET_DIR}/M_BloodBrush_Circle"
RUNTIME_TEST_PATH = f"{ASSET_DIR}/M_BloodPaint_RuntimeTest"
MANAGER_BP_PATH = f"{ASSET_DIR}/BP_BloodPaintManager"


def log(message):
    unreal.log(f"[ProphecyBloodTexturePainting] {message}")


def ensure_dir(path):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)


def set_prop(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception:
        return False


def create_or_load(name, path, cls, factory):
    full_path = f"{path}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(full_path):
        asset = unreal.EditorAssetLibrary.load_asset(full_path)
        if isinstance(asset, cls):
            return asset

    return unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, path, cls, factory)


def recreate_asset(name, path, cls, factory):
    full_path = f"{path}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(full_path):
        if not unreal.EditorAssetLibrary.delete_asset(full_path):
            raise RuntimeError(f"Could not delete stale asset {full_path}")
        if unreal.EditorAssetLibrary.does_asset_exist(full_path):
            raise RuntimeError(f"Stale asset still exists after delete attempt: {full_path}")

    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, path, cls, factory)
    if not asset:
        raise RuntimeError(f"Could not recreate asset {full_path}")
    return asset


def const(material, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionConstant, x, y)
    node.set_editor_property("r", float(value))
    return node


def const2(material, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionConstant2Vector, x, y)
    node.set_editor_property("r", float(value[0]))
    node.set_editor_property("g", float(value[1]))
    return node


def const3(material, color, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, x, y)
    set_prop(node, "constant", color)
    return node


def scalar_param(material, name, default, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionScalarParameter, x, y)
    set_prop(node, "parameter_name", name)
    set_prop(node, "default_value", float(default))
    return node


def vector_param(material, name, color, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionVectorParameter, x, y)
    set_prop(node, "parameter_name", name)
    set_prop(node, "default_value", color)
    return node


def enable_surface_usages(material):
    try:
        unreal.MaterialEditingLibrary.set_material_usage(material, unreal.MaterialUsage.MATUSAGE_STATIC_MESH)
        unreal.MaterialEditingLibrary.set_material_usage(material, unreal.MaterialUsage.MATUSAGE_NANITE)
    except Exception as exc:
        log(f"Could not set material usage flags on {material.get_name()}: {exc}")


def f_input(function, name, input_type, preview, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionFunctionInput, x, y)
    set_prop(node, "input_name", name)
    set_prop(node, "input_type", input_type)
    set_prop(node, "preview_value", preview)
    set_prop(node, "use_preview_value_as_default", False)
    return node


def f_output(function, name, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionFunctionOutput, x, y)
    set_prop(node, "output_name", name)
    return node


def f_scalar_param(function, name, default, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionScalarParameter, x, y)
    set_prop(node, "parameter_name", name)
    set_prop(node, "default_value", float(default))
    return node


def f_vector_param(function, name, color, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionVectorParameter, x, y)
    set_prop(node, "parameter_name", name)
    set_prop(node, "default_value", color)
    return node


def build_mask_blend_function():
    function = create_or_load(
        "MF_BloodPaintMaskBlend",
        ASSET_DIR,
        unreal.MaterialFunction,
        unreal.MaterialFunctionFactoryNew(),
    )
    if not function:
        raise RuntimeError("Could not create MF_BloodPaintMaskBlend")

    unreal.MaterialEditingLibrary.delete_all_material_expressions_in_function(function)

    in_base = f_input(function, "OriginalBaseColor", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR3, unreal.LinearColor(0.62, 0.58, 0.52, 1), -900, -260)
    in_rough = f_input(function, "OriginalRoughness", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, unreal.LinearColor(0.55, 0, 0, 0), -900, -80)
    in_mask = f_input(function, "BloodMask", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, unreal.LinearColor(0, 0, 0, 0), -900, 100)
    in_color = f_input(function, "BloodColor", unreal.FunctionInputType.FUNCTION_INPUT_VECTOR3, unreal.LinearColor(0.18, 0.005, 0.002, 1), -900, 280)
    in_blood_rough = f_input(function, "BloodRoughness", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, unreal.LinearColor(0.14, 0, 0, 0), -900, 460)
    in_intensity = f_input(function, "BloodIntensity", unreal.FunctionInputType.FUNCTION_INPUT_SCALAR, unreal.LinearColor(1, 0, 0, 0), -900, 640)

    multiply = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionMultiply, -520, 240)
    saturate = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionSaturate, -330, 240)
    base_lerp = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionLinearInterpolate, -90, -170)
    rough_lerp = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionLinearInterpolate, -90, 250)
    out_base = f_output(function, "BaseColorOut", 210, -160)
    out_rough = f_output(function, "RoughnessOut", 210, 250)

    unreal.MaterialEditingLibrary.connect_material_expressions(in_mask, "", multiply, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(in_intensity, "", multiply, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(multiply, "", saturate, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(in_base, "", base_lerp, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(in_color, "", base_lerp, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(saturate, "", base_lerp, "Alpha")
    unreal.MaterialEditingLibrary.connect_material_expressions(in_rough, "", rough_lerp, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(in_blood_rough, "", rough_lerp, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(saturate, "", rough_lerp, "Alpha")
    unreal.MaterialEditingLibrary.connect_material_expressions(base_lerp, "", out_base, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(rough_lerp, "", out_rough, "None")

    unreal.MaterialEditingLibrary.layout_material_function_expressions(function)
    unreal.MaterialEditingLibrary.update_material_function(function)
    unreal.EditorAssetLibrary.save_loaded_asset(function)
    log(f"Saved {MF_PATH}")
    return function


def build_surface_function():
    function = recreate_asset(
        "MF_BloodPaintSurface",
        ASSET_DIR,
        unreal.MaterialFunction,
        unreal.MaterialFunctionFactoryNew(),
    )
    if not function:
        raise RuntimeError("Could not create MF_BloodPaintSurface")

    blood_color = f_vector_param(function, "BloodColor", unreal.LinearColor(0.18, 0.005, 0.002, 1), -920, -610)
    blood_noise_color = f_vector_param(function, "BloodNoiseColor", unreal.LinearColor(0.55, 0.035, 0.012, 1), -920, -430)
    blood_rough = f_scalar_param(function, "BloodRoughness", 0.14, -920, -180)
    blood_spec = f_scalar_param(function, "BloodSpecular", 0.65, -920, 0)
    blood_metal = f_scalar_param(function, "BloodMetallic", 0.0, -920, 180)
    noise_scale = f_scalar_param(function, "BloodNoiseScale", 0.035, -920, 420)
    noise_strength = f_scalar_param(function, "BloodNoiseStrength", 0.18, -920, 600)

    world_position = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionWorldPosition, -920, 780)
    position_scale = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionMultiply, -650, 460)
    noise = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionNoise, -430, 460)
    set_prop(noise, "scale", 1.0)
    set_prop(noise, "quality", 1)
    set_prop(noise, "levels", 2)
    set_prop(noise, "output_min", 0.0)
    set_prop(noise, "output_max", 1.0)

    noise_alpha_mul = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionMultiply, -200, 520)
    noise_alpha = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionSaturate, 0, 520)
    blood_tint = unreal.MaterialEditingLibrary.create_material_expression_in_function(function, unreal.MaterialExpressionLinearInterpolate, 220, -500)

    out_base = f_output(function, "BaseColorOut", 820, -380)
    out_rough = f_output(function, "RoughnessOut", 820, -120)
    out_spec = f_output(function, "SpecularOut", 820, 120)
    out_metal = f_output(function, "MetallicOut", 820, 360)

    unreal.MaterialEditingLibrary.connect_material_expressions(world_position, "", position_scale, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(noise_scale, "", position_scale, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(position_scale, "", noise, "Position")
    unreal.MaterialEditingLibrary.connect_material_expressions(noise, "", noise_alpha_mul, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(noise_strength, "", noise_alpha_mul, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(noise_alpha_mul, "", noise_alpha, "None")

    unreal.MaterialEditingLibrary.connect_material_expressions(blood_color, "", blood_tint, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(blood_noise_color, "", blood_tint, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(noise_alpha, "", blood_tint, "Alpha")

    unreal.MaterialEditingLibrary.connect_material_expressions(blood_tint, "", out_base, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(blood_rough, "", out_rough, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(blood_spec, "", out_spec, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(blood_metal, "", out_metal, "None")

    unreal.MaterialEditingLibrary.layout_material_function_expressions(function)
    unreal.MaterialEditingLibrary.update_material_function(function)
    unreal.EditorAssetLibrary.save_loaded_asset(function)
    log(f"Saved {MF_SURFACE_PATH}")
    return function


def build_test_material(name, mask_value):
    material = create_or_load(name, ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew())
    if not material:
        raise RuntimeError(f"Could not create {name}")

    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    set_prop(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    set_prop(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_prop(material, "shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)

    base = const3(material, unreal.LinearColor(0.62, 0.58, 0.52, 1), -500, -240)
    blood = const3(material, unreal.LinearColor(0.18, 0.005, 0.002, 1), -500, -80)
    mask = const(material, mask_value, -500, 80)
    rough_clean = const(material, 0.58, -500, 230)
    rough_blood = const(material, 0.14, -500, 380)
    base_lerp = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate, -190, -170)
    rough_lerp = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate, -190, 230)

    unreal.MaterialEditingLibrary.connect_material_expressions(base, "", base_lerp, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(blood, "", base_lerp, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(mask, "", base_lerp, "Alpha")
    unreal.MaterialEditingLibrary.connect_material_expressions(rough_clean, "", rough_lerp, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(rough_blood, "", rough_lerp, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(mask, "", rough_lerp, "Alpha")
    unreal.MaterialEditingLibrary.connect_material_property(base_lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(rough_lerp, "", unreal.MaterialProperty.MP_ROUGHNESS)

    enable_surface_usages(material)
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    log(f"Saved {ASSET_DIR}/{name}")
    return material


def build_brush_material():
    if unreal.EditorAssetLibrary.does_asset_exist(BRUSH_PATH):
        material = unreal.EditorAssetLibrary.load_asset(BRUSH_PATH)
        if material:
            log(f"Reusing existing {BRUSH_PATH}")
            return material

    material = create_or_load("M_BloodBrush_Circle", ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew())
    if not material:
        raise RuntimeError("Could not create M_BloodBrush_Circle")

    set_prop(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    set_prop(material, "blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    set_prop(material, "shading_model", unreal.MaterialShadingModel.MSM_UNLIT)

    texcoord = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionTextureCoordinate, -640, -80)
    custom = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionCustom, -380, -80)
    custom_input = unreal.CustomInput()
    custom_input.set_editor_property("input_name", "UV")
    set_prop(custom, "inputs", [custom_input])
    set_prop(custom, "output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    set_prop(custom, "description", "HardCircle")
    set_prop(custom, "code", "float2 p = (UV - 0.5) * 2.0; return dot(p, p) <= 1.0 ? 1.0 : 0.0;")

    unreal.MaterialEditingLibrary.connect_material_expressions(texcoord, "", custom, "UV")
    unreal.MaterialEditingLibrary.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(custom, "", unreal.MaterialProperty.MP_OPACITY)

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    log(f"Saved {BRUSH_PATH}")
    return material


def build_runtime_test_material():
    if unreal.EditorAssetLibrary.does_asset_exist(RUNTIME_TEST_PATH):
        material = unreal.EditorAssetLibrary.load_asset(RUNTIME_TEST_PATH)
        if material:
            log(f"Reusing existing {RUNTIME_TEST_PATH}")
            return material

    material = create_or_load("M_BloodPaint_RuntimeTest", ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew())
    if not material:
        raise RuntimeError("Could not create M_BloodPaint_RuntimeTest")

    set_prop(material, "material_domain", unreal.MaterialDomain.MD_SURFACE)
    set_prop(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_prop(material, "shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)

    texcoord = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionTextureCoordinate, -1120, -210)
    set_prop(texcoord, "coordinate_index", 0)
    mask_tex = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionTextureSampleParameter2D, -900, -230)
    set_prop(mask_tex, "parameter_name", "BloodMaskRT")
    set_prop(mask_tex, "texture", unreal.EditorAssetLibrary.load_asset("/Engine/EngineResources/Black.Black"))

    original_base = const3(material, unreal.LinearColor(0.62, 0.58, 0.52, 1), -900, -20)
    original_rough = const(material, 0.58, -900, 130)
    blood_color = vector_param(material, "BloodColor", unreal.LinearColor(0.18, 0.005, 0.002, 1), -900, 300)
    blood_rough = scalar_param(material, "BloodRoughness", 0.14, -900, 470)
    intensity = scalar_param(material, "BloodIntensity", 1.0, -900, 640)
    debug_mask = scalar_param(material, "DebugShowBloodMask", 0.0, -900, 810)
    half = const(material, 0.5, -690, 910)

    multiply = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionMultiply, -600, -120)
    saturate = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionSaturate, -420, -120)
    base_lerp = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate, -180, 40)
    rough_lerp = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate, -180, 380)
    debug_lerp = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate, 60, 40)

    unreal.MaterialEditingLibrary.connect_material_expressions(texcoord, "", mask_tex, "UVs")
    unreal.MaterialEditingLibrary.connect_material_expressions(mask_tex, "R", multiply, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(intensity, "", multiply, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(multiply, "", saturate, "None")
    unreal.MaterialEditingLibrary.connect_material_expressions(original_base, "", base_lerp, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(blood_color, "", base_lerp, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(saturate, "", base_lerp, "Alpha")
    unreal.MaterialEditingLibrary.connect_material_expressions(original_rough, "", rough_lerp, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(blood_rough, "", rough_lerp, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(saturate, "", rough_lerp, "Alpha")
    unreal.MaterialEditingLibrary.connect_material_expressions(base_lerp, "", debug_lerp, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(saturate, "", debug_lerp, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(debug_mask, "", debug_lerp, "Alpha")
    unreal.MaterialEditingLibrary.connect_material_property(debug_lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(rough_lerp, "", unreal.MaterialProperty.MP_ROUGHNESS)

    enable_surface_usages(material)
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    log(f"Saved {RUNTIME_TEST_PATH}")
    return material


def build_manager_blueprint():
    manager_class = getattr(unreal, "ProphecyBloodTexturePaintManager", None)
    if not manager_class:
        log("Skipped BP_BloodPaintManager: ProphecyBloodTexturePaintManager C++ class is not loaded yet")
        return None

    if unreal.EditorAssetLibrary.does_asset_exist(MANAGER_BP_PATH):
        blueprint = unreal.EditorAssetLibrary.load_asset(MANAGER_BP_PATH)
    else:
        factory = unreal.BlueprintFactory()
        factory.set_editor_property("parent_class", manager_class)
        blueprint = unreal.AssetToolsHelpers.get_asset_tools().create_asset("BP_BloodPaintManager", ASSET_DIR, unreal.Blueprint, factory)

    if blueprint:
        unreal.EditorAssetLibrary.save_loaded_asset(blueprint)
        log(f"Saved {MANAGER_BP_PATH}")
    return blueprint


def main():
    ensure_dir(ASSET_DIR)
    build_mask_blend_function()
    build_surface_function()
    build_test_material("M_Test_BloodMaskBlend_Clean", 0.0)
    build_test_material("M_Test_BloodMaskBlend_FullBlood", 1.0)
    build_brush_material()
    build_runtime_test_material()
    build_manager_blueprint()


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
