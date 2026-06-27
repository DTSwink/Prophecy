import json
import os
import traceback

import unreal


ASSET_DIR = "/Game/_mygame/blood2/PP_Fluid"
STENCIL_VALUE = 42


def log(message):
    unreal.log(f"[ProphecyBloodFluidPP] {message}")


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
        if asset is None:
            asset = unreal.load_asset(path)
        if asset is None:
            asset_data = unreal.EditorAssetLibrary.find_asset_data(path)
            if asset_data and asset_data.is_valid():
                asset = asset_data.get_asset()
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
    set_prop(node, "b_filtered", filtered)
    return node


def user_scene_texture(material, name, x, y, filtered=True, clamped=True):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionUserSceneTexture, x, y
    )
    set_prop(node, "user_scene_texture", name)
    set_prop(node, "filtered", filtered)
    set_prop(node, "b_filtered", filtered)
    set_prop(node, "clamped", clamped)
    set_prop(node, "b_clamped", clamped)
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


def configure_post_process_material(material, priority, user_output=None, divisor=(0, 0)):
    material.modify()
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    set_prop(material, "material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    set_prop(material, "blendable_location", unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)
    set_prop(material, "blendable_priority", int(priority))
    set_prop(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    if user_output:
        set_prop(material, "user_scene_texture", user_output)
        set_prop(material, "user_texture_divisor", unreal.IntPoint(int(divisor[0]), int(divisor[1])))
    else:
        set_prop(material, "user_scene_texture", "None")
        set_prop(material, "user_texture_divisor", unreal.IntPoint(0, 0))


def finish_material(material):
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)


def build_stencil_debug():
    material = create_or_load_material("M_PP_Blood_StencilDebug42")
    configure_post_process_material(material, 5)

    force_stencil = scene_texture(material, unreal.SceneTextureId.PPI_CUSTOM_STENCIL, -700, 0, False)
    node = custom(
        material,
        "Stencil42Debug",
        f"""
float2 uv = GetDefaultSceneTextureUV(Parameters, PPI_PostProcessInput0);
float stencil = ForceStencil.Fetch(0.0, 0.0).r;
float rawStencil = (stencil <= 1.0) ? (stencil * 255.0) : stencil;
float mask = abs(rawStencil - {float(STENCIL_VALUE)}) < 0.5 ? 1.0 : 0.0;
return float4(mask.xxx, 1.0);
""",
        unreal.CustomMaterialOutputType.CMOT_FLOAT4,
        ["ForceStencil"],
        -360,
        0,
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(force_stencil, "", node, "ForceStencil")
    unreal.MaterialEditingLibrary.connect_material_property(node, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish_material(material)
    return material


def build_extract():
    material = create_or_load_material("M_PP_Blood_Extract")
    configure_post_process_material(material, 10, "BloodExtract", (2, 2))

    force_scene = scene_texture(material, unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0, -900, -120, False)
    force_stencil = scene_texture(material, unreal.SceneTextureId.PPI_CUSTOM_STENCIL, -900, 80, False)
    node = custom(
        material,
        "BloodExtract",
        f"""
float4 scene = ForceScene.Fetch(0.0, 0.0);
float stencil = ForceStencil.Fetch(0.0, 0.0).r;
float rawStencil = (stencil <= 1.0) ? (stencil * 255.0) : stencil;
float mask = abs(rawStencil - {float(STENCIL_VALUE)}) < 0.5 ? 1.0 : 0.0;
return float4(scene.rgb * mask, mask);
""",
        unreal.CustomMaterialOutputType.CMOT_FLOAT4,
        ["ForceScene", "ForceStencil"],
        -520,
        0,
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(force_scene, "", node, "ForceScene")
    unreal.MaterialEditingLibrary.connect_material_expressions(force_stencil, "", node, "ForceStencil")
    unreal.MaterialEditingLibrary.connect_material_property(node, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish_material(material)
    return material


def build_scene_copy():
    material = create_or_load_material("M_PP_Blood_SceneCopy")
    configure_post_process_material(material, 8, "BloodScene", (1, 1))

    scene = scene_texture(material, unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0, -900, 0, False)
    node = custom(
        material,
        "BloodSceneCopy",
        """
float2 uv = GetDefaultSceneTextureUV(Parameters, PPI_PostProcessInput0);
float4 scene = SceneTextureLookup(uv, PPI_PostProcessInput0, false);
return float4(scene.rgb, 1.0);
""",
        unreal.CustomMaterialOutputType.CMOT_FLOAT4,
        ["Scene"],
        -520,
        0,
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(scene, "", node, "Scene")
    unreal.MaterialEditingLibrary.connect_material_property(node, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish_material(material)
    return material


def build_blur(name, source_name, output_name, priority, axis):
    material = create_or_load_material(name)
    configure_post_process_material(material, priority, output_name, (2, 2))

    source = user_scene_texture(material, source_name, -900, 0, True, True)
    radius = scalar_param(material, "BlurRadius", 4.0, -900, 160)
    axis_code = "float2(1.0, 0.0)" if axis == "h" else "float2(0.0, 1.0)"
    node = custom(
        material,
        name,
        f"""
float2 axis = {axis_code};
float r = max(BlurRadius, 0.0);
float4 c = 0.0;
c += SceneTextureFetch(Source.ID, axis * r * -2.0) * 0.06136;
c += SceneTextureFetch(Source.ID, axis * r * -1.0) * 0.24477;
c += Source.Fetch(0.0, 0.0)                         * 0.38774;
c += SceneTextureFetch(Source.ID, axis * r *  1.0) * 0.24477;
c += SceneTextureFetch(Source.ID, axis * r *  2.0) * 0.06136;
return c;
""",
        unreal.CustomMaterialOutputType.CMOT_FLOAT4,
        ["Source", "BlurRadius"],
        -520,
        0,
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(source, "", node, "Source")
    unreal.MaterialEditingLibrary.connect_material_expressions(radius, "", node, "BlurRadius")
    unreal.MaterialEditingLibrary.connect_material_property(node, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish_material(material)
    return material


def build_composite():
    material = create_or_load_material("M_PP_Blood_Composite")
    configure_post_process_material(material, 40)

    scene = scene_texture(material, unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0, -1100, -180, False)
    stencil = scene_texture(material, unreal.SceneTextureId.PPI_CUSTOM_STENCIL, -1100, 0, False)
    radius = scalar_param(material, "BlurRadius", 4.0, -1100, 180)
    threshold = scalar_param(material, "Threshold", 0.32, -1100, 320)
    softness = scalar_param(material, "Softness", 0.08, -1100, 460)
    sample_quality = scalar_param(material, "BlurSampleQuality", 1.0, -1100, 600)
    blood_color = vector_param(material, "BloodLayerColor", unreal.LinearColor(1.0, 0.045, 0.015, 1.0), -1100, 740)

    node = custom(
        material,
        "BloodSinglePassLayerBlur",
        f"""
float2 uv = GetDefaultSceneTextureUV(Parameters, PPI_PostProcessInput0);
float2 texel = GetSceneTextureViewSize(PPI_PostProcessInput0).zw;
float3 scene = SceneTextureLookup(uv, PPI_PostProcessInput0, false).rgb;
float sceneDepthHere = SceneTextureLookup(uv, PPI_SceneDepth, false).r;
float stencilHere = SceneTextureLookup(uv, PPI_CustomStencil, false).r;
float rawStencilHere = (stencilHere <= 1.0) ? (stencilHere * 255.0) : stencilHere;
float sourceMaskHere = abs(rawStencilHere - {float(STENCIL_VALUE)}) < 0.5 ? 1.0 : 0.0;
float bloodDepthHere = SceneTextureLookup(uv, PPI_CustomDepth, false).r;
float sourceBloodSignalHere = saturate((scene.r - max(scene.g, scene.b)) * 8.0);

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
        float2 sampleUv = uv + tap * texel * radius * 2.0;
        float stencil = SceneTextureLookup(sampleUv, PPI_CustomStencil, false).r;
        float rawStencil = (stencil <= 1.0) ? (stencil * 255.0) : stencil;
        float sampleMask = abs(rawStencil - {float(STENCIL_VALUE)}) < 0.5 ? 1.0 : 0.0;
        float bloodDepth = SceneTextureLookup(sampleUv, PPI_CustomDepth, false).r;
        float3 sampleScene = SceneTextureLookup(sampleUv, PPI_PostProcessInput0, false).rgb;
        float sampleBloodSignal = saturate((sampleScene.r - max(sampleScene.g, sampleScene.b)) * 8.0);
        sampleMask *= sampleBloodSignal;
        layerAlpha += sampleMask * w;
        layerRgb += sampleScene * sampleMask * w;
        layerDepth += bloodDepth * sampleMask * w;
        layerDepthWeight += sampleMask * w;
        weightSum += w;
    }}
}}

layerAlpha = saturate(layerAlpha / max(weightSum, 0.0001));
float3 layerColor = layerRgb / max(layerDepthWeight, 0.0001);
float blurredBloodDepth = layerDepth / max(layerDepthWeight, 0.0001);
float soft = max(Softness, 0.0001);
float lower = max(Threshold - soft, 0.0);
float upper = max(Threshold + soft, lower + 0.0001);
float coverage = smoothstep(lower, upper, layerAlpha);
coverage *= step(0.000001, layerAlpha);
coverage *= step(blurredBloodDepth, sceneDepthHere + depthBias);
float sourceVisibleHere = sourceMaskHere * sourceBloodSignalHere * step(bloodDepthHere, sceneDepthHere + depthBias);
float outputCoverage = max(coverage, sourceVisibleHere);
return float4(lerp(scene, layerColor, outputCoverage), 1.0);
""",
        unreal.CustomMaterialOutputType.CMOT_FLOAT4,
        ["Scene", "Stencil", "BlurRadius", "Threshold", "Softness", "BlurSampleQuality", "BloodLayerColor"],
        -600,
        180,
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(scene, "", node, "Scene")
    unreal.MaterialEditingLibrary.connect_material_expressions(stencil, "", node, "Stencil")
    unreal.MaterialEditingLibrary.connect_material_expressions(radius, "", node, "BlurRadius")
    unreal.MaterialEditingLibrary.connect_material_expressions(threshold, "", node, "Threshold")
    unreal.MaterialEditingLibrary.connect_material_expressions(softness, "", node, "Softness")
    unreal.MaterialEditingLibrary.connect_material_expressions(sample_quality, "", node, "BlurSampleQuality")
    unreal.MaterialEditingLibrary.connect_material_expressions(blood_color, "", node, "BloodLayerColor")
    unreal.MaterialEditingLibrary.connect_material_property(node, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish_material(material)
    return material


def append_journal(created_paths):
    journal = os.path.join(unreal.Paths.project_dir(), "ProjectJournal.md")
    with open(journal, "a", encoding="utf-8") as f:
        f.write("\n## 2026-06-26 - Blood GPU Fake-Fluid Post Process\n")
        f.write("- Enabled persistent CustomDepth stencil in config with `r.CustomDepth=3`.\n")
        f.write("- Baked `NS_bloodsplat` defaults to render custom depth with stencil value 42.\n")
        f.write("- Enabled `Allow Custom Depth Writes` on translucent `M_blood_final`.\n")
        f.write("- Generated PP materials for stencil debug plus Extract -> BlurH -> BlurV -> layer-style Composite under `/Game/_mygame/blood2/PP_Fluid`.\n")
        f.write("- Kept the existing `_PPM_blood` as scratch/debug and avoided depending on DecalManager stencil nodes.\n")
        f.write("- Created assets: " + ", ".join(created_paths) + "\n")


def build_all():
    ensure_dir(ASSET_DIR)
    created = [
        build_stencil_debug(),
        build_extract(),
        build_blur("M_PP_Blood_BlurH", "BloodExtract", "BloodBlurH", 20, "h"),
        build_blur("M_PP_Blood_BlurV", "BloodBlurH", "BloodBlurV", 30, "v"),
        build_composite(),
    ]
    paths = [asset.get_path_name().split(".")[0] for asset in created]
    append_journal(paths)
    unreal.EditorAssetLibrary.save_directory(ASSET_DIR)
    return paths


if not globals().get("PROPHECY_BLOOD_PP_SKIP_AUTORUN", False):
    try:
        paths = build_all()
        print(json.dumps({"ok": True, "assets": paths}, indent=2))
    except Exception:
        unreal.log_error(traceback.format_exc())
        raise
