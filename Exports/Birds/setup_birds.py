"""Ambient birds asset setup for Prophecy (UE 5.7). Headless:
UnrealEditor-Cmd.exe <uproject> -ExecutePythonScript="<this file>" -BirdSetupQuit -unattended -nosplash -nocef -nullrhi
Safe to re-run: replaces only assets under DEST.

Creates under /Game/Prophecy/Creatures/Birds:
  Materials/M_Bird_Body, M_Bird_Feathers (masked, two-sided), M_BirdFeatherFX (instanced burst, per-instance cell + colours)
  SM_BirdFeatherFX
  <Species>/SK_<Species> (+ skeleton), A_<Species>_Perch|Walk|Glide|Flap|Hover, MI_<Species>_Body|Eye|Feathers|FeatherFX, Textures/
Recolouring: textures carry masks (M.R primary tint weight, M.G secondary tint weight, M.B detail luminance); the material lerps
to PrimaryColour / SecondaryColour by TintStrength (set per bird at runtime; 0 for gulls).
"""
import json
import os
import unreal

SRC = os.path.dirname(os.path.abspath(__file__))
DEST = "/Game/Prophecy/Creatures/Birds"
SPECIES = ["Gull", "Kingfisher"]
CLIPS = ["Perch", "Walk", "Glide", "Flap", "Hover"]
REPORT = os.path.join(unreal.Paths.project_saved_dir(), "BirdTest", "setup.json")
AT = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary
MP = unreal.MaterialProperty
report = {"errors": [], "warnings": []}


def log(m):
    unreal.log("[Birds] " + m)


def warn(m):
    unreal.log_warning("[Birds] " + m)
    report["warnings"].append(m)


unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX False")


def task(filename, dest_path, dest_name, options=None):
    t = unreal.AssetImportTask()
    t.filename = filename
    t.destination_path = dest_path
    t.destination_name = dest_name
    t.replace_existing = True
    t.replace_existing_settings = True
    t.automated = True
    t.save = False
    if options is not None:
        t.options = options
    return t


def import_textures(sp):
    names = ["T_%s_Body_BC" % sp, "T_%s_Body_N" % sp, "T_%s_Body_M" % sp, "T_%s_Feathers_BC" % sp, "T_%s_Feathers_N" % sp, "T_%s_Feathers_M" % sp]
    AT.import_asset_tasks([task(os.path.join(SRC, sp, n + ".png"), f"{DEST}/{sp}/Textures", n) for n in names])
    tex = {}
    for n in names:
        a = unreal.load_asset(f"{DEST}/{sp}/Textures/{n}")
        if a is None:
            report["errors"].append("texture import failed: " + n)
            continue
        if n.endswith("_N"):
            a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            a.set_editor_property("srgb", False)
            a.set_editor_property("flip_green_channel", False)
        elif n.endswith("_M"):
            a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
            a.set_editor_property("srgb", False)
        a.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_CHARACTER)
        tex[n.split("_", 2)[2]] = a
    return tex


RECOLOUR = r"""
float d = saturate(M.b) * 2.0;
float3 t = lerp(BC, P * d, saturate(M.r) * K);
t = lerp(t, S * d, saturate(M.g) * K);
return t;
"""
# Blood stains: up to 4 spheres (xyz = centre in the mesh's reference pose = PreSkinnedPosition, w = radius) set by ABird
# on its MIDs. Irregular soaked edge + a diluted halo on the plumage. Same code in both nodes (colour / mask).
BLOOD_FN = r"""
float4 st[4] = { S0, S1, S2, S3 };
float core = 0.0;
float halo = 0.0;
for (int i = 0; i < 4; i++)
{
    float r = st[i].w;
    if (r > 0.0001)
    {
        float3 d = P - st[i].xyz;
        float dist = length(d);
        float3 n = d / max(dist, 0.0001);
        float ph = i * 1.913 + st[i].x * 0.37;
        float rip = 0.20 * sin(n.x * 6.3 + n.y * 2.9 + ph) + 0.14 * sin(n.y * 8.7 - n.z * 4.6 + ph * 1.7) + 0.10 * sin(n.z * 13.1 + n.x * 5.3 + ph * 2.3);
        float rr = r * (1.0 + rip);
        core = max(core, saturate((rr - dist) / (0.18 * r)));
        halo = max(halo, saturate((rr * 1.45 - dist) / (0.35 * r)));
    }
}
"""
BLOOD_COLOUR = BLOOD_FN + r"""
float3 c = lerp(BC, BC * float3(0.75, 0.2, 0.18) + float3(0.08, 0.0, 0.0), halo * 0.55);
return lerp(c, B.rgb, core * 0.97);
"""
BLOOD_MASK = BLOOD_FN + r"""
return core;
"""
FX_UV = r"""
float c = floor(D0 + 0.5);
float col = fmod(c, 8.0);
float row = floor(c / 8.0);
return float2((col + UV.x) / 8.0, (row + UV.y) / 2.0);
"""


def new_material(name):
    path = f"{DEST}/Materials/{name}"
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    m = AT.create_asset(name, DEST + "/Materials", unreal.Material, unreal.MaterialFactoryNew())
    for flag in ("used_with_skeletal_mesh", "used_with_instanced_static_meshes"):
        try:
            m.set_editor_property(flag, True)
        except Exception as e:
            warn(f"{name}.{flag}: {e}")
    return m


def custom(m, code, out_type, names, x, y, desc):
    c = MEL.create_material_expression(m, unreal.MaterialExpressionCustom, x, y)
    c.set_editor_property("code", code)
    c.set_editor_property("output_type", out_type)
    c.set_editor_property("description", desc)
    ins = []
    for n in names:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        ins.append(ci)
    c.set_editor_property("inputs", ins)
    return c


def tex_param(m, name, x, y, kind=None, uv=None):
    s = MEL.create_material_expression(m, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    s.set_editor_property("parameter_name", name)
    default = unreal.load_asset("/Engine/EngineResources/DefaultTexture")
    if kind == "normal":
        s.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        default = unreal.load_asset("/Engine/EngineMaterials/DefaultNormal")
    elif kind == "masks":
        s.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
        default = unreal.load_asset("/Engine/EngineResources/Black")
    if default:
        s.set_editor_property("texture", default)
    if uv is not None:
        MEL.connect_material_expressions(uv, "", s, "UVs")
    return s


def vparam(m, name, value, x, y):
    v = MEL.create_material_expression(m, unreal.MaterialExpressionVectorParameter, x, y)
    v.set_editor_property("parameter_name", name)
    v.set_editor_property("default_value", unreal.LinearColor(*value, 1.0))
    return v


def sparam(m, name, value, x, y):
    s = MEL.create_material_expression(m, unreal.MaterialExpressionScalarParameter, x, y)
    s.set_editor_property("parameter_name", name)
    s.set_editor_property("default_value", value)
    return s


def build_bird_material(name, masked):
    m = new_material(name)
    if masked:
        m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
        m.set_editor_property("two_sided", True)
        m.set_editor_property("opacity_mask_clip_value", 0.33)
    bc = tex_param(m, "BaseColorTex", -900, -300)
    mk = tex_param(m, "MaskTex", -900, 0, "masks")
    nm = tex_param(m, "NormalTex", -900, 300, "normal")
    p = vparam(m, "PrimaryColour", (0.36, 0.13, 0.05), -900, 550)
    s = vparam(m, "SecondaryColour", (0.95, 0.94, 0.92), -900, 700)
    k = sparam(m, "TintStrength", 0.0, -900, 850)
    rc = custom(m, RECOLOUR, unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["BC", "M", "P", "S", "K"], -450, -100, "Bird recolour")
    MEL.connect_material_expressions(bc, "RGB", rc, "BC")
    MEL.connect_material_expressions(mk, "RGB", rc, "M")
    MEL.connect_material_expressions(p, "", rc, "P")
    MEL.connect_material_expressions(s, "", rc, "S")
    MEL.connect_material_expressions(k, "", rc, "K")
    # blood stains (reference-pose position, interpolated from the vertex shader)
    pre = MEL.create_material_expression(m, unreal.MaterialExpressionPreSkinnedPosition, -1300, 1000)
    vi = MEL.create_material_expression(m, unreal.MaterialExpressionVertexInterpolator, -1100, 1000)
    MEL.connect_material_expressions(pre, "", vi, "")
    stains = [vparam(m, "BloodStain%d" % i, (0.0, 0.0, 0.0), -1100, 1150 + i * 140) for i in range(4)]
    packed = []
    for i, st in enumerate(stains):
        st.set_editor_property("default_value", unreal.LinearColor(0.0, 0.0, 0.0, 0.0))
        app = MEL.create_material_expression(m, unreal.MaterialExpressionAppendVector, -800, 1150 + i * 140)
        if not (MEL.connect_material_expressions(st, "RGB", app, "A") and MEL.connect_material_expressions(st, "A", app, "B")):
            warn("blood stain %d: append failed" % i)
        packed.append(app)
    bcol = vparam(m, "BloodColour", (0.11, 0.006, 0.004), -1100, 1750)
    bn = custom(m, BLOOD_COLOUR, unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["BC", "P", "S0", "S1", "S2", "S3", "B"], -200, -100, "Blood stains")
    bm = custom(m, BLOOD_MASK, unreal.CustomMaterialOutputType.CMOT_FLOAT1, ["P", "S0", "S1", "S2", "S3"], -200, 250, "Blood mask")
    MEL.connect_material_expressions(rc, "", bn, "BC")
    MEL.connect_material_expressions(bcol, "", bn, "B")
    for node in (bn, bm):
        MEL.connect_material_expressions(vi, "", node, "P")
        for i, app in enumerate(packed):
            MEL.connect_material_expressions(app, "", node, "S%d" % i)
    rough = MEL.create_material_expression(m, unreal.MaterialExpressionLinearInterpolate, 0, 250)
    MEL.connect_material_expressions(sparam(m, "Roughness", 0.78, -450, 200), "", rough, "A")
    MEL.connect_material_expressions(sparam(m, "BloodRoughness", 0.3, -450, 400), "", rough, "B")
    MEL.connect_material_expressions(bm, "", rough, "Alpha")
    MEL.connect_material_property(bn, "", MP.MP_BASE_COLOR)
    MEL.connect_material_property(nm, "RGB", MP.MP_NORMAL)
    MEL.connect_material_property(rough, "", MP.MP_ROUGHNESS)
    MEL.connect_material_property(sparam(m, "Specular", 0.3, -450, 300), "", MP.MP_SPECULAR)
    if masked:
        MEL.connect_material_property(bc, "A", MP.MP_OPACITY_MASK)
    MEL.recompile_material(m)
    return m


def build_fx_material():
    m = new_material("M_BirdFeatherFX")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    m.set_editor_property("two_sided", True)
    m.set_editor_property("opacity_mask_clip_value", 0.33)
    d = []
    for i in range(8):
        e = MEL.create_material_expression(m, unreal.MaterialExpressionPerInstanceCustomData, -1500, -300 + i * 90)
        e.set_editor_property("data_index", i)
        d.append(e)
    tc = MEL.create_material_expression(m, unreal.MaterialExpressionTextureCoordinate, -1500, 500)
    uv = custom(m, FX_UV, unreal.CustomMaterialOutputType.CMOT_FLOAT2, ["D0", "UV"], -1200, 300, "Feather atlas cell")
    MEL.connect_material_expressions(d[0], "", uv, "D0")
    MEL.connect_material_expressions(tc, "", uv, "UV")
    bc = tex_param(m, "BaseColorTex", -900, -300, uv=uv)
    mk = tex_param(m, "MaskTex", -900, 0, "masks", uv=uv)
    nm = tex_param(m, "NormalTex", -900, 300, "normal", uv=uv)
    rc = custom(m, r"""
float3 P = float3(D1, D2, D3);
float3 S = float3(D4, D5, D6);
float d = saturate(M.b) * 2.0;
float3 t = lerp(BC, P * d, saturate(M.r) * D7);
t = lerp(t, S * d, saturate(M.g) * D7);
return t;
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["BC", "M", "D1", "D2", "D3", "D4", "D5", "D6", "D7"], -450, -100, "Feather recolour")
    MEL.connect_material_expressions(bc, "RGB", rc, "BC")
    MEL.connect_material_expressions(mk, "RGB", rc, "M")
    for i in range(1, 8):
        MEL.connect_material_expressions(d[i], "", rc, "D%d" % i)
    MEL.connect_material_property(rc, "", MP.MP_BASE_COLOR)
    MEL.connect_material_property(nm, "RGB", MP.MP_NORMAL)
    MEL.connect_material_property(bc, "A", MP.MP_OPACITY_MASK)
    MEL.connect_material_property(sparam(m, "Roughness", 0.7, -450, 200), "", MP.MP_ROUGHNESS)
    MEL.connect_material_property(sparam(m, "Specular", 0.3, -450, 300), "", MP.MP_SPECULAR)
    MEL.recompile_material(m)
    return m


def make_mi(parent, path_dir, name, tex_set, scalars=None):
    full = f"{path_dir}/{name}"
    if EAL.does_asset_exist(full):
        EAL.delete_asset(full)
    mi = AT.create_asset(name, path_dir, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, parent)
    for pname, t in tex_set.items():
        MEL.set_material_instance_texture_parameter_value(mi, pname, t)
    for pname, v in (scalars or {}).items():
        MEL.set_material_instance_scalar_parameter_value(mi, pname, v)
    MEL.update_material_instance(mi)
    return mi


def import_skeletal(sp, mats):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", False)
    ui.set_editor_property("create_physics_asset", False)
    sk = ui.get_editor_property("skeletal_mesh_import_data")
    sk.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    sk.set_editor_property("import_morph_targets", False)
    sk.set_editor_property("convert_scene", True)
    t = task(os.path.join(SRC, sp, f"SK_{sp}.fbx"), f"{DEST}/{sp}", f"SK_{sp}", ui)
    AT.import_asset_tasks([t])
    mesh = unreal.load_asset(f"{DEST}/{sp}/SK_{sp}")
    if not isinstance(mesh, unreal.SkeletalMesh):
        report["errors"].append(f"{sp}: skeletal import failed {list(t.get_editor_property('imported_object_paths'))}")
        return None
    # SkeletalMaterial entries come back as copies: build a fresh array and set it as a whole
    slots = mesh.get_editor_property("materials")
    names, fresh = [], []
    for s in slots:
        nm = str(s.get_editor_property("material_slot_name"))
        names.append(nm)
        mat = None
        for key, m in mats.items():
            if key.lower() in nm.lower():
                mat = m
        e = unreal.SkeletalMaterial()
        e.set_editor_property("material_interface", mat)
        e.set_editor_property("material_slot_name", s.get_editor_property("material_slot_name"))
        for prop in ("imported_material_slot_name", "uv_channel_data"):
            try:
                e.set_editor_property(prop, s.get_editor_property(prop))
            except Exception:
                pass
        fresh.append(e)
    mesh.set_editor_property("materials", fresh)
    applied = [(str(x.get_editor_property("material_slot_name")), x.get_editor_property("material_interface").get_name() if x.get_editor_property("material_interface") else None)
               for x in mesh.get_editor_property("materials")]
    if any(a[1] is None for a in applied):
        report["errors"].append(f"{sp}: material slots not assigned {applied}")
    skel = mesh.get_editor_property("skeleton")
    info = {"slots": applied, "skeleton": skel.get_path_name() if skel else None}
    try:
        b = mesh.get_bounds()
        info["bounds_extent"] = [round(v, 2) for v in (b.box_extent.x, b.box_extent.y, b.box_extent.z)]
        info["bounds_origin"] = [round(v, 2) for v in (b.origin.x, b.origin.y, b.origin.z)]
    except Exception as e:
        info["bounds"] = str(e)
    try:
        ref = unreal.SkeletalMeshEditorSubsystem  # bone names via skeleton modifier is not exposed everywhere: use socket query
        info["bones"] = [str(n) for n in unreal.SkeletalMeshEditorSubsystem.get_bone_names(mesh)] if hasattr(unreal.SkeletalMeshEditorSubsystem, "get_bone_names") else None
    except Exception as e:
        info["bones"] = str(e)
    report[f"SK_{sp}"] = info
    return mesh


def import_anims(sp, mesh):
    skel = mesh.get_editor_property("skeleton")
    out = {}
    for clip in CLIPS:
        ui = unreal.FbxImportUI()
        ui.set_editor_property("automated_import_should_detect_type", False)
        ui.set_editor_property("import_mesh", False)
        ui.set_editor_property("import_as_skeletal", False)
        ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_ANIMATION)
        ui.set_editor_property("original_import_type", unreal.FBXImportType.FBXIT_ANIMATION)
        ui.set_editor_property("import_animations", True)
        ui.set_editor_property("import_materials", False)
        ui.set_editor_property("import_textures", False)
        ui.set_editor_property("skeleton", skel)
        an = ui.get_editor_property("anim_sequence_import_data")
        an.set_editor_property("animation_length", unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
        an.set_editor_property("convert_scene", True)
        try:
            an.set_editor_property("remove_redundant_keys", False)
        except Exception:
            pass
        name = f"A_{sp}_{clip}"
        dest = f"{DEST}/{sp}"
        for a in EAL.list_assets(dest, recursive=False):
            if str(a).split("/")[-1].split(".")[0] in (name, name + "_Anim", name + "_PhysicsAsset", name + "_Skeleton"):
                EAL.delete_asset(str(a).split(".")[0])
        t = task(os.path.join(SRC, sp, name + ".fbx"), dest, name, ui)
        AT.import_asset_tasks([t])
        paths = [str(p) for p in t.get_editor_property("imported_object_paths")]
        seq = None
        for p in paths:
            a = unreal.load_asset(p)
            if isinstance(a, unreal.AnimSequence):
                seq = a
        if seq is None:
            report["errors"].append(f"{name}: anim import failed {paths}")
            continue
        want = f"{dest}/{name}"
        if seq.get_path_name().split(".")[0] != want:
            EAL.rename_asset(seq.get_path_name().split(".")[0], want)
            seq = unreal.load_asset(want)
        try:
            seq.set_editor_property("enable_root_motion", False)
        except Exception:
            pass
        out[clip] = {"path": seq.get_path_name(), "length": round(seq.get_play_length(), 4)}
    report[f"anims_{sp}"] = out


def import_fx_mesh():
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    sm = ui.get_editor_property("static_mesh_import_data")
    sm.set_editor_property("combine_meshes", True)
    sm.set_editor_property("generate_lightmap_u_vs", False)
    sm.set_editor_property("auto_generate_collision", False)
    sm.set_editor_property("convert_scene", True)
    try:
        sm.set_editor_property("build_nanite", False)
    except Exception:
        pass
    AT.import_asset_tasks([task(os.path.join(SRC, "SM_BirdFeatherFX.fbx"), DEST, "SM_BirdFeatherFX", ui)])
    mesh = unreal.load_asset(f"{DEST}/SM_BirdFeatherFX")
    if not isinstance(mesh, unreal.StaticMesh):
        report["errors"].append("SM_BirdFeatherFX import failed")
        return None
    b = mesh.get_bounding_box()
    report["SM_BirdFeatherFX"] = [round(v, 3) for v in (b.min.x, b.min.y, b.min.z, b.max.x, b.max.y, b.max.z)]
    return mesh


try:
    body_m = build_bird_material("M_Bird_Body", False)
    fea_m = build_bird_material("M_Bird_Feathers", True)
    fx_m = build_fx_material()
    fx_mesh = import_fx_mesh()
    for sp in SPECIES:
        tex = import_textures(sp)
        d = f"{DEST}/{sp}"
        body_set = {"BaseColorTex": tex.get("Body_BC"), "NormalTex": tex.get("Body_N"), "MaskTex": tex.get("Body_M")}
        fea_set = {"BaseColorTex": tex.get("Feathers_BC"), "NormalTex": tex.get("Feathers_N"), "MaskTex": tex.get("Feathers_M")}
        mi_body = make_mi(body_m, d, f"MI_{sp}_Body", body_set, {"Roughness": 0.82})
        mi_eye = make_mi(body_m, d, f"MI_{sp}_Eye", body_set, {"Roughness": 0.06, "Specular": 0.7})
        mi_fea = make_mi(fea_m, d, f"MI_{sp}_Feathers", fea_set, {"Roughness": 0.68})
        make_mi(fx_m, d, f"MI_{sp}_FeatherFX", fea_set, {"Roughness": 0.7})
        mesh = import_skeletal(sp, {"_Body": mi_body, "_Eye": mi_eye, "_Feathers": mi_fea})
        if mesh:
            import_anims(sp, mesh)
    # LODs + texture caps (same code as setup_bird_lods.py on its own)
    try:
        import runpy
        lods = runpy.run_path(os.path.join(SRC, "setup_bird_lods.py"), run_name="bird_lods")
        lrep = {"errors": [], "warnings": [], "meshes": {}}
        lods["apply"](lrep)
        report["lods"] = lrep["meshes"]
        report["errors"] += lrep["errors"]
        report["warnings"] += lrep["warnings"]
    except Exception:
        import traceback
        report["errors"].append("lods: " + traceback.format_exc())
    saved = EAL.save_directory(DEST, only_if_is_dirty=False, recursive=True)
    report["saved"] = bool(saved)
    report["assets"] = [str(p) for p in EAL.list_assets(DEST, recursive=True)]
except Exception:
    import traceback
    report["errors"].append(traceback.format_exc())
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=1)
log("report -> " + REPORT)
unreal.log("BIRDSETUP errors=%d warnings=%d" % (len(report["errors"]), len(report["warnings"])))
if "-BirdSetupQuit" in unreal.SystemLibrary.get_command_line():
    unreal.SystemLibrary.quit_editor()
