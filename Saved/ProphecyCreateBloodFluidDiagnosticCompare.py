import json
import os
import traceback

import unreal


ASSET_DIR = "/Game/_mygame/blood2/PP_Fluid"
DIAG_MATERIAL_NAME = "M_PP_Blood_Diag_SplitCompare"
DIAG_MATERIAL_PATH = f"{ASSET_DIR}/{DIAG_MATERIAL_NAME}.{DIAG_MATERIAL_NAME}"
DEFAULT_COMPOSITE_PATH = "/Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Composite.M_PP_Blood_Composite"
STENCIL_VALUE = 42
STATE_FILE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "BloodFluidAB",
    "diagnostic_compare_state.json",
)


def log(message):
    unreal.log(f"[ProphecyBloodFluidDiag] {message}")


def set_prop(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception as exc:
        log(f"Could not set {obj.get_name()}.{name}: {exc}")
        return False


def ensure_dir(path):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)


def create_or_load_material(name):
    path = f"{ASSET_DIR}/{name}"
    object_path = f"{path}.{name}"
    asset = unreal.load_object(None, object_path)
    if isinstance(asset, unreal.Material):
        return asset

    if unreal.EditorAssetLibrary.does_asset_exist(path):
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if isinstance(asset, unreal.Material):
            return asset
        raise RuntimeError(f"Existing asset at {path} did not load as a Material: {asset}")

    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name,
        ASSET_DIR,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not isinstance(asset, unreal.Material):
        raise RuntimeError(f"Could not create material asset at {path}: {asset}")
    return asset


def scalar_param(material, name, default, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, x, y
    )
    set_prop(node, "parameter_name", name)
    set_prop(node, "default_value", float(default))
    return node


def vector_param(material, name, color, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, x, y
    )
    set_prop(node, "parameter_name", name)
    set_prop(node, "default_value", color)
    return node


def scene_texture(material, scene_texture_id, x, y, filtered=False):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionSceneTexture, x, y
    )
    set_prop(node, "scene_texture_id", scene_texture_id)
    set_prop(node, "filtered", filtered)
    return node


def custom(material, desc, code, output_type, input_names, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionCustom, x, y
    )
    inputs = []
    for input_name in input_names:
        custom_input = unreal.CustomInput()
        custom_input.set_editor_property("input_name", input_name)
        inputs.append(custom_input)
    set_prop(node, "inputs", inputs)
    set_prop(node, "output_type", output_type)
    set_prop(node, "description", desc)
    set_prop(node, "code", code)
    return node


def configure_post_process_material(material, priority):
    material.modify()
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    set_prop(material, "material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    set_prop(material, "blendable_location", unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)
    set_prop(material, "blendable_priority", int(priority))
    set_prop(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_prop(material, "blendable_output_alpha", False)


def finish_material(material):
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)


def build_diag_material():
    ensure_dir(ASSET_DIR)
    material = create_or_load_material(DIAG_MATERIAL_NAME)
    configure_post_process_material(material, 2000)

    scene = scene_texture(material, unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0, -1200, -240, False)
    stencil = scene_texture(material, unreal.SceneTextureId.PPI_CUSTOM_STENCIL, -1200, -60, False)
    scene_depth = scene_texture(material, unreal.SceneTextureId.PPI_SCENE_DEPTH, -1200, 120, False)
    custom_depth = scene_texture(material, unreal.SceneTextureId.PPI_CUSTOM_DEPTH, -1200, 300, False)
    stage = scalar_param(material, "DiagStage", 0.0, -1200, 480)
    radius = scalar_param(material, "BlurRadius", 4.0, -1200, 640)
    threshold = scalar_param(material, "Threshold", 0.32, -1200, 800)
    softness = scalar_param(material, "Softness", 0.08, -1200, 960)
    sample_quality = scalar_param(material, "BlurSampleQuality", 1.0, -1200, 1120)
    blood_color = vector_param(material, "BloodLayerColor", unreal.LinearColor(1.0, 0.045, 0.015, 1.0), -1200, 1280)

    node = custom(
        material,
        "BloodDiagnosticSplitCompare",
        f"""
float3 scene = Scene.Fetch(0.0, 0.0).rgb;

int stage = (int)floor(clamp(DiagStage, 0.0, 7.0) + 0.5);
float3 outColor = scene;

if (stage > 0)
{{
    float sceneDepthHere = SceneDepth.Fetch(0.0, 0.0).r;
    float stencilHere = Stencil.Fetch(0.0, 0.0).r;
    float rawStencilHere = (stencilHere <= 1.0) ? (stencilHere * 255.0) : stencilHere;
    float sourceMaskHere = abs(rawStencilHere - {float(STENCIL_VALUE)}) < 0.5 ? 1.0 : 0.0;
    float bloodDepthHere = BloodDepth.Fetch(0.0, 0.0).r;
    float sourceBloodSignalHere = saturate((scene.r - max(scene.g, scene.b)) * 8.0);

    if (stage == 1)
    {{
        outColor = lerp(scene, float3(1.0, 0.0, 0.0), sourceMaskHere * 0.85);
    }}
    else if (stage == 2)
    {{
        outColor = scene * sourceMaskHere;
    }}
    else if (stage == 3)
    {{
        outColor = scene * sourceMaskHere * sourceBloodSignalHere;
    }}
    else if (stage >= 4)
    {{
        float radius = max(BlurRadius, 0.0);
        float quality = max(BlurSampleQuality, 0.0);
        int halfTapCount = (int)ceil(clamp(2.0 + 3.0 * quality, 2.0, 14.0));
        float layerAlpha = 0.0;
        float weightSum = 0.0;
        float layerDepth = 0.0;
        float layerDepthWeight = 0.0;
        float3 layerRgb = 0.0;
        float depthBias = 2.0;

        for (int y = -halfTapCount; y <= halfTapCount; ++y)
        {{
            for (int x = -halfTapCount; x <= halfTapCount; ++x)
            {{
                float2 tap = float2((float)x, (float)y) / max((float)halfTapCount, 0.0001);
                float w = exp(-dot(tap, tap) * 2.75);
                float2 pixelOffset = tap * radius * 2.0;
                float stencil = Stencil.Fetch(pixelOffset.x, pixelOffset.y).r;
                float rawStencil = (stencil <= 1.0) ? (stencil * 255.0) : stencil;
                float sampleMask = abs(rawStencil - {float(STENCIL_VALUE)}) < 0.5 ? 1.0 : 0.0;
                float bloodDepth = BloodDepth.Fetch(pixelOffset.x, pixelOffset.y).r;
                float3 sampleScene = Scene.Fetch(pixelOffset.x, pixelOffset.y).rgb;
                float sampleBloodSignal = saturate((sampleScene.r - max(sampleScene.g, sampleScene.b)) * 8.0);

                if (stage >= 5)
                {{
                    sampleMask *= sampleBloodSignal;
                }}

                layerAlpha += sampleMask * w;
                layerRgb += sampleScene * sampleMask * w;
                layerDepth += bloodDepth * sampleMask * w;
                layerDepthWeight += sampleMask * w;
                weightSum += w;
            }}
        }}

        layerAlpha = saturate(layerAlpha / max(weightSum, 0.0001));
        float3 layerColor = (stage == 4) ? BloodLayerColor.rgb : (layerRgb / max(layerDepthWeight, 0.0001));
        float blurredBloodDepth = layerDepth / max(layerDepthWeight, 0.0001);
        float coverage = layerAlpha;

        if (stage >= 6)
        {{
            float soft = max(Softness, 0.0001);
            float lower = max(Threshold - soft, 0.0);
            float upper = max(Threshold + soft, lower + 0.0001);
            coverage = smoothstep(lower, upper, layerAlpha);
            coverage *= step(0.000001, layerAlpha);
        }}

        if (stage >= 7)
        {{
            coverage *= step(blurredBloodDepth, sceneDepthHere + depthBias);
            float sourceVisibleHere = sourceMaskHere * sourceBloodSignalHere * step(bloodDepthHere, sceneDepthHere + depthBias);
            coverage = max(coverage, sourceVisibleHere);
        }}

        outColor = lerp(scene, layerColor, coverage);
    }}
}}

return float4(outColor, 1.0);
""",
        unreal.CustomMaterialOutputType.CMOT_FLOAT4,
        ["Scene", "Stencil", "SceneDepth", "BloodDepth", "DiagStage", "BlurRadius", "Threshold", "Softness", "BlurSampleQuality", "BloodLayerColor"],
        -760,
        160,
    )

    unreal.MaterialEditingLibrary.connect_material_expressions(scene, "", node, "Scene")
    unreal.MaterialEditingLibrary.connect_material_expressions(stencil, "", node, "Stencil")
    unreal.MaterialEditingLibrary.connect_material_expressions(scene_depth, "", node, "SceneDepth")
    unreal.MaterialEditingLibrary.connect_material_expressions(custom_depth, "", node, "BloodDepth")
    unreal.MaterialEditingLibrary.connect_material_expressions(stage, "", node, "DiagStage")
    unreal.MaterialEditingLibrary.connect_material_expressions(radius, "", node, "BlurRadius")
    unreal.MaterialEditingLibrary.connect_material_expressions(threshold, "", node, "Threshold")
    unreal.MaterialEditingLibrary.connect_material_expressions(softness, "", node, "Softness")
    unreal.MaterialEditingLibrary.connect_material_expressions(sample_quality, "", node, "BlurSampleQuality")
    unreal.MaterialEditingLibrary.connect_material_expressions(blood_color, "", node, "BloodLayerColor")
    unreal.MaterialEditingLibrary.connect_material_property(node, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish_material(material)
    return material


def editor_and_pie_worlds():
    worlds = []
    try:
        worlds += list(unreal.EditorLevelLibrary.get_pie_worlds(True))
    except Exception:
        pass
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        if world:
            worlds.append(world)
    except Exception:
        pass

    result = []
    seen = set()
    for world in worlds:
        if not world or world.get_path_name() in seen:
            continue
        seen.add(world.get_path_name())
        result.append(world)
    return result


def controllers():
    result = []
    for world in editor_and_pie_worlds():
        try:
            actors = list(unreal.ActorIterator(world))
        except Exception:
            continue
        for actor in actors:
            if actor.get_class().get_name() == "ProphecyBloodFluidPostProcessController":
                result.append(actor)
    return result


def get_prop_first(obj, names, default=None):
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception:
            pass
    return default


def set_prop_first(obj, names, value):
    for name in names:
        try:
            obj.set_editor_property(name, value)
            return name
        except Exception:
            pass
    return None


def active_mid(controller):
    ppc = get_prop_first(controller, ("post_process_component", "PostProcessComponent"))
    if not ppc:
        return None
    try:
        weighted = ppc.get_editor_property("settings").get_editor_property("weighted_blendables")
        for item in weighted.get_editor_property("array"):
            obj = item.get_editor_property("object")
            if obj and "M_PP_Blood_Diag_SplitCompare" in obj.get_path_name():
                return obj
    except Exception:
        pass
    return None


def sync_diag_parameters(controller, mid, stage):
    if not mid:
        return
    mid.set_scalar_parameter_value("DiagStage", float(stage))
    for prop_name, scalar_name in (
        ("blur_radius", "BlurRadius"),
        ("threshold", "Threshold"),
        ("softness", "Softness"),
        ("blur_sample_quality", "BlurSampleQuality"),
    ):
        value = get_prop_first(controller, (prop_name,), None)
        if value is not None:
            mid.set_scalar_parameter_value(scalar_name, float(value))


def save_state(entries):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def enable_diagnostic(stage=0):
    material = build_diag_material()
    entries = []
    for controller in controllers():
        old = get_prop_first(controller, ("composite_material",), None)
        old_path = old.get_path_name() if old and hasattr(old, "get_path_name") else str(old)
        entries.append({"controller": controller.get_path_name(), "old_composite": old_path})
        controller.modify()
        set_prop_first(controller, ("composite_material",), material)
        set_prop_first(controller, ("blood_fluid_post_enabled",), True)
        set_prop_first(controller, ("show_stencil_debug",), False)
        controller.apply_blood_fluid_post_process_settings()
        sync_diag_parameters(controller, active_mid(controller), stage)
    save_state(entries)
    return {"stage": int(stage), "material": material.get_path_name(), "controllers": entries}


def set_stage(stage):
    result = []
    for controller in controllers():
        sync_diag_parameters(controller, active_mid(controller), stage)
        result.append(controller.get_path_name())
    return {"stage": int(stage), "controllers": result}


def restore():
    material = unreal.load_asset(DEFAULT_COMPOSITE_PATH)
    if not material:
        raise RuntimeError(f"Missing default composite material: {DEFAULT_COMPOSITE_PATH}")
    result = []
    for controller in controllers():
        controller.modify()
        set_prop_first(controller, ("composite_material",), material)
        controller.apply_blood_fluid_post_process_settings()
        result.append(controller.get_path_name())
    return {"restored_composite": DEFAULT_COMPOSITE_PATH, "controllers": result}


def main():
    action = str(globals().get("ACTION", "enable")).lower()
    stage = int(globals().get("STAGE", 0))
    if action == "build":
        result = {"material": build_diag_material().get_path_name()}
    elif action == "enable":
        result = enable_diagnostic(stage)
    elif action == "stage":
        result = set_stage(stage)
    elif action == "restore":
        result = restore()
    else:
        raise ValueError("ACTION must be build, enable, stage, or restore")
    print(json.dumps({"ok": True, "action": action, "result": result}, indent=2))


if not globals().get("PROPHECY_BLOOD_DIAG_SKIP_AUTORUN", False):
    try:
        main()
    except Exception:
        unreal.log_error(traceback.format_exc())
        raise
