"""Falling-leaf assets: meshes (one per blade shape), the atlas made from the trees' own scanned hornbeam leaves, and
M_Leaf (two-sided foliage, per-instance senescence / wetness / atlas cell / dithered fade).
Run: UnrealEditor-Cmd <uproject> -ExecutePythonScript=Exports/Leaves/setup_leaves.py -LeafSetupQuit -unattended -nullrhi"""
import os, json
import unreal

SRC = os.path.dirname(os.path.abspath(__file__))
DEST = "/Game/Prophecy/Ambient/Leaves"
SHAPES = ["Flat", "Wavy", "Cupped", "Rolled", "Twisted", "Wet"]
REPORT = os.path.join(unreal.Paths.project_saved_dir(), "LeafTest", "setup.json")
AT = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary
MP = unreal.MaterialProperty
rep = {"errors": [], "warnings": []}
unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX False")


def task(filename, dest_path, dest_name, options=None):
    t = unreal.AssetImportTask()
    t.filename = filename; t.destination_path = dest_path; t.destination_name = dest_name
    t.replace_existing = True; t.replace_existing_settings = True; t.automated = True; t.save = False
    if options is not None: t.options = options
    return t


def import_textures():
    out = {}
    for n in ["T_Leaves_BC", "T_Leaves_N", "T_Leaves_M"]:
        AT.import_asset_tasks([task(os.path.join(SRC, n + ".png"), DEST + "/Textures", n)])
        a = unreal.load_asset(f"{DEST}/Textures/{n}")
        if a is None:
            rep["errors"].append("texture import failed " + n); continue
        if n.endswith("_N"):
            a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP); a.set_editor_property("srgb", False)
        elif n.endswith("_M"):
            a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS); a.set_editor_property("srgb", False)
        else:
            a.set_editor_property("srgb", True)
        a.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD)
        out[n] = a
    return out


def import_mesh(shape):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True); ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("import_materials", False); ui.set_editor_property("import_textures", False)
    sm = ui.get_editor_property("static_mesh_import_data")
    sm.set_editor_property("combine_meshes", True)
    sm.set_editor_property("auto_generate_collision", False)
    sm.set_editor_property("generate_lightmap_u_vs", False)
    sm.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    sm.set_editor_property("convert_scene", True)
    name = "SM_Leaf_" + shape
    AT.import_asset_tasks([task(os.path.join(SRC, name + ".fbx"), DEST, name, ui)])
    m = unreal.load_asset(f"{DEST}/{name}")
    if not isinstance(m, unreal.StaticMesh):
        rep["errors"].append("mesh import failed " + name); return None
    b = m.get_bounding_box()
    rep[name] = [round(v, 2) for v in (b.min.x, b.min.y, b.min.z, b.max.x, b.max.y, b.max.z)]
    return m


ATLAS_UV = r"""
float c = floor(Cell + 0.5);
return float2((fmod(c, 4.0) + UV.x) / 4.0, (floor(c / 4.0) + UV.y) / 2.0);
"""
# colour work done in display (sRGB-like) space so the palette reads like the reference leaves, back to linear at the end
LEAF_COLOUR = r"""
float3 bc = pow(max(BC, 0.0), 1.0 / 2.2);
float st = saturate(Sen * 1.6 - (1.0 - M.g) * 0.8);
float3 G0 = float3(0.16, 0.30, 0.05), Y0 = float3(0.80, 0.62, 0.10), O0 = float3(0.74, 0.34, 0.06), B0 = float3(0.30, 0.15, 0.06);
float3 pal = st < 0.33 ? lerp(G0, Y0, st / 0.33) : (st < 0.66 ? lerp(Y0, O0, (st - 0.33) / 0.33) : lerp(O0, B0, (st - 0.66) / 0.34));
pal *= 1.0 + Hue * float3(0.07, -0.01, -0.05);
float lum = dot(bc, float3(0.3, 0.59, 0.11));
float detail = clamp(lum / 0.28, 0.45, 1.8);
float3 col = pal * detail;
col = lerp(col, float3(0.85, 0.80, 0.45) * detail, 0.25 * M.r);
col = lerp(col, bc, saturate(1.0 - st / 0.25));
col *= 1.0 - 0.65 * M.a * saturate(Spots * 1.4);
col = pow(max(col, 0.0), 2.2);
// wet: darker and a little deeper in colour (water fills the surface roughness)
col = lerp(col, col * col * 2.2, 0.35 * Wet) * (1.0 - 0.35 * Wet);
return col;
"""
SUBSURF = r"""
return Col * float3(1.25, 1.0, 0.55) * (0.35 + 0.75 * saturate(M.b)) * (1.0 - 0.6 * Wet);
"""
# dithered fade (resolved smooth by temporal AA), interleaved-gradient noise per pixel and frame
DITHER = r"""
float2 p = Parameters.SvPosition.xy + 5.588238 * float(View.StateFrameIndexMod8);
float n = frac(52.9829189 * frac(dot(p, float2(0.06711056, 0.00583715))));
return (A > 0.5 && Fade > n) ? 1.0 : 0.0;
"""


def custom(m, code, out_type, names, x, y, desc):
    c = MEL.create_material_expression(m, unreal.MaterialExpressionCustom, x, y)
    c.set_editor_property("code", code); c.set_editor_property("output_type", out_type); c.set_editor_property("description", desc)
    ins = []
    for n in names:
        ci = unreal.CustomInput(); ci.set_editor_property("input_name", n); ins.append(ci)
    c.set_editor_property("inputs", ins)
    return c


def tex(m, t, x, y, uv, kind):
    s = MEL.create_material_expression(m, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    s.set_editor_property("parameter_name", t.get_name())
    if kind == "normal": s.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    elif kind == "masks": s.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    s.set_editor_property("texture", t)
    MEL.connect_material_expressions(uv, "", s, "UVs")
    return s


def build_material(tx):
    path = f"{DEST}/M_Leaf"
    if EAL.does_asset_exist(path): EAL.delete_asset(path)
    m = AT.create_asset("M_Leaf", DEST, unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("used_with_instanced_static_meshes", True)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    m.set_editor_property("two_sided", True)
    m.set_editor_property("opacity_mask_clip_value", 0.5)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    d = []
    for i in range(6):
        e = MEL.create_material_expression(m, unreal.MaterialExpressionPerInstanceCustomData, -1700, -400 + i * 110)
        e.set_editor_property("data_index", i)
        d.append(e)
    tc = MEL.create_material_expression(m, unreal.MaterialExpressionTextureCoordinate, -1700, 400)
    uv = custom(m, ATLAS_UV, unreal.CustomMaterialOutputType.CMOT_FLOAT2, ["UV", "Cell"], -1400, 300, "Leaf atlas cell")
    MEL.connect_material_expressions(tc, "", uv, "UV")
    MEL.connect_material_expressions(d[2], "", uv, "Cell")
    bc = tex(m, tx["T_Leaves_BC"], -1100, -300, uv, None)
    mk = tex(m, tx["T_Leaves_M"], -1100, 0, uv, "masks")
    nm = tex(m, tx["T_Leaves_N"], -1100, 300, uv, "normal")
    col = custom(m, LEAF_COLOUR, unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["BC", "M", "Sen", "Wet", "Hue", "Spots"], -700, -250, "Senescence / wet colour")
    MEL.connect_material_expressions(bc, "RGB", col, "BC")
    MEL.connect_material_expressions(mk, "RGBA", col, "M")
    for name, idx in (("Sen", 0), ("Wet", 1), ("Hue", 4), ("Spots", 5)):
        MEL.connect_material_expressions(d[idx], "", col, name)
    ss = custom(m, SUBSURF, unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["Col", "M", "Wet"], -400, 150, "Back-lit transmission")
    MEL.connect_material_expressions(col, "", ss, "Col"); MEL.connect_material_expressions(mk, "RGBA", ss, "M"); MEL.connect_material_expressions(d[1], "", ss, "Wet")
    dz = custom(m, DITHER, unreal.CustomMaterialOutputType.CMOT_FLOAT1, ["A", "Fade"], -400, 450, "Dithered fade")
    MEL.connect_material_expressions(bc, "A", dz, "A"); MEL.connect_material_expressions(d[3], "", dz, "Fade")
    rough = MEL.create_material_expression(m, unreal.MaterialExpressionLinearInterpolate, -400, -450)
    c1 = MEL.create_material_expression(m, unreal.MaterialExpressionConstant, -600, -500); c1.set_editor_property("r", 0.62)
    c2 = MEL.create_material_expression(m, unreal.MaterialExpressionConstant, -600, -430); c2.set_editor_property("r", 0.2)
    MEL.connect_material_expressions(c1, "", rough, "A"); MEL.connect_material_expressions(c2, "", rough, "B"); MEL.connect_material_expressions(d[1], "", rough, "Alpha")
    spec = MEL.create_material_expression(m, unreal.MaterialExpressionLinearInterpolate, -400, -600)
    s1 = MEL.create_material_expression(m, unreal.MaterialExpressionConstant, -600, -650); s1.set_editor_property("r", 0.35)
    s2 = MEL.create_material_expression(m, unreal.MaterialExpressionConstant, -600, -580); s2.set_editor_property("r", 0.6)
    MEL.connect_material_expressions(s1, "", spec, "A"); MEL.connect_material_expressions(s2, "", spec, "B"); MEL.connect_material_expressions(d[1], "", spec, "Alpha")
    MEL.connect_material_property(col, "", MP.MP_BASE_COLOR)
    MEL.connect_material_property(nm, "RGB", MP.MP_NORMAL)
    MEL.connect_material_property(rough, "", MP.MP_ROUGHNESS)
    MEL.connect_material_property(spec, "", MP.MP_SPECULAR)
    MEL.connect_material_property(ss, "", MP.MP_SUBSURFACE_COLOR)
    MEL.connect_material_property(dz, "", MP.MP_OPACITY_MASK)
    MEL.recompile_material(m)
    mi_path = f"{DEST}/MI_Leaf_Hornbeam"
    if EAL.does_asset_exist(mi_path): EAL.delete_asset(mi_path)
    mi = AT.create_asset("MI_Leaf_Hornbeam", DEST, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, m)
    MEL.update_material_instance(mi)
    return m, mi


try:
    tx = import_textures()
    meshes = [import_mesh(s) for s in SHAPES]
    if len(tx) == 3:
        m, mi = build_material(tx)
        for sm in meshes:
            if sm:
                sm.set_material(0, mi)
                try:
                    ns = sm.get_editor_property("nanite_settings"); ns.enabled = False; sm.set_editor_property("nanite_settings", ns)
                except Exception as e:
                    rep["warnings"].append("nanite: " + str(e))
    rep["saved"] = bool(EAL.save_directory(DEST, only_if_is_dirty=False, recursive=True))
    rep["assets"] = [str(p) for p in EAL.list_assets(DEST, recursive=True)]
except Exception:
    import traceback
    rep["errors"].append(traceback.format_exc())
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w", encoding="utf-8") as f: json.dump(rep, f, indent=1)
unreal.log("LEAFSETUP errors=%d %s" % (len(rep["errors"]), json.dumps(rep)[:1500]))
if "-LeafSetupQuit" in unreal.SystemLibrary.get_command_line():
    unreal.SystemLibrary.quit_editor()
