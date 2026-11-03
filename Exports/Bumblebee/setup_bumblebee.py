"""Bumblebee asset setup for Prophecy (UE 5.7). Run headless:
UnrealEditor-Cmd.exe <uproject> -ExecutePythonScript="<this file>" -BeeSetupQuit -unattended -nosplash -nocef -nullrhi
(not the pythonscript commandlet: UE 5.7 Interchange texture import needs a Slate application)
or from the editor (Tools > Execute Python Script). Safe to re-run: replaces only assets in DEST.

Creates in DEST:
  Textures/  T_Bumblebee_*                  (normal maps are DirectX, ORM linear)
  Materials/ M_Bumblebee_Body/Fur/Wing      (World Position Offset v2: wing beat Hz + leg stepping driven by
                                             per-instance custom data, inert on the skeletal mesh)
  SK_Bumblebee (+LOD1/2, skeleton, Fly / Idle_Landed anims)   hero / cinematic use
  SM_Bumblebee_Fly, SM_Bumblebee_Landed (4 LODs each)          used by ABumblebeeSwarm (instanced)
"""
import json
import os
import unreal

SRC = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(SRC, "Static")
DEST = "/Game/Prophecy/Creatures/Bumblebee"
REPORT = os.path.join(unreal.Paths.project_saved_dir(), "BeeTest", "setup.json")

AT = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary
MP = unreal.MaterialProperty
report = {"errors": [], "warnings": []}


def log(msg):
    unreal.log("[Bumblebee] " + msg)


def warn(msg):
    unreal.log_warning("[Bumblebee] " + msg)
    report["warnings"].append(msg)


# Legacy FBX importer honours FbxImportUI (normals/vertex colours/LOD import) exactly.
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


# ----------------------------------------------------------------------------------------------- textures
def import_textures():
    names = ["T_Bumblebee_Body_BC", "T_Bumblebee_Body_N", "T_Bumblebee_Body_ORM",
             "T_Bumblebee_Fur_BC", "T_Bumblebee_Fur_N", "T_Bumblebee_Wing_BC"]
    AT.import_asset_tasks([task(os.path.join(SRC, n + ".png"), DEST + "/Textures", n) for n in names])
    tex = {}
    for n in names:
        a = unreal.load_asset(f"{DEST}/Textures/{n}")
        if a is None:
            report["errors"].append("texture import failed: " + n)
            continue
        if n.endswith("_N"):
            a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            a.set_editor_property("srgb", False)
            a.set_editor_property("flip_green_channel", False)
        elif n.endswith("_ORM"):
            a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
            a.set_editor_property("srgb", False)
        a.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_CHARACTER)
        tex[n] = a
    log("textures: %d" % len(tex))
    return tex


# ----------------------------------------------------------------------------------------------- materials
WPO_HLSL = r"""
float3 o = 0;
float sd = P.y >= 0 ? 1.0 : -1.0;
float hz = D3 > 1.0 ? D3 : 150.0;
if (G > 0.25 && D0 > 0.001)
{
    // wings: rotate about the hinge (elevation about the body axis + fore/aft sweep) at the bee's beat frequency
    float fore = G > 0.75 ? 1.0 : 0.0;
    float3 h = lerp(float3(0.0, 0.31, 0.25), float3(0.24, 0.30, 0.29), fore);
    h.y *= sd;
    float ph = frac(T * hz + R * 7.31) * 6.2831853 - (1.0 - fore) * 0.35;
    float el = radians(12.0 + 55.0 * cos(ph)) * sd;
    float sw = radians(24.0 * sin(ph)) * sd;
    float3 d = P - h;
    float c = cos(el);
    float s = sin(el);
    d = float3(d.x, d.y * c - d.z * s, d.y * s + d.z * c);
    c = cos(sw);
    s = sin(sw);
    d = float3(d.x * c - d.y * s, d.x * s + d.y * c, d.z);
    o += (h + d - P) * D0;
}
if (Bw > 0.001)
{
    // legs: alternating tripod gait. D1 = leg cycles walked (distance / stride), D2 = stride (model cm) x walk amount.
    // stance (first half): foot slides back linearly by one half-stride per half-cycle = exactly the body's advance -> planted
    // swing (second half): foot returns forward, lifted
    float p = frac(D1 + (A > 0.5 ? 0.5 : 0.0));
    float a = 0.25 * D2;
    float x;
    float z = 0.0;
    if (p < 0.5)
    {
        x = a * (1.0 - 4.0 * p);
    }
    else
    {
        float q = (p - 0.5) * 2.0;
        x = -a * cos(q * 3.14159265);
        z = 0.45 * a * sin(q * 3.14159265);
    }
    o.x += Bw * x;
    o.z += Bw * z;
    // gentle dangle while flying
    o.x += Bw * D0 * 0.05 * sin(T * 7.0 + R * 6.0 + A * 2.0);
    o.z += Bw * D0 * 0.03 * sin(T * 5.3 + R * 4.0);
}
return o.x * AX + o.y * AY + o.z * AZ;
"""

WING_OPACITY_HLSL = r"""
// fast-beating wings are seen as a translucent blur: fade the membrane while flapping above ~40 Hz
float hz = D3 > 1.0 ? D3 : 150.0;
return O * lerp(1.0, 0.5, saturate(D0) * saturate((hz - 40.0) / 80.0));
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


def sample(m, texture, x, y, kind=None):
    s = MEL.create_material_expression(m, unreal.MaterialExpressionTextureSample, x, y)
    s.set_editor_property("texture", texture)
    if kind == "normal":
        s.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    elif kind == "masks":
        s.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    return s


def const(m, v, x, y):
    c = MEL.create_material_expression(m, unreal.MaterialExpressionConstant, x, y)
    c.set_editor_property("r", v)
    return c


def add_wpo(m, x=-1400, y=600):
    custom = MEL.create_material_expression(m, unreal.MaterialExpressionCustom, x + 700, y)
    custom.set_editor_property("code", WPO_HLSL)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    custom.set_editor_property("description", "Bee WPO (wings/legs)")
    names = ["P", "G", "Bw", "A", "D0", "D1", "D2", "D3", "T", "R", "AX", "AY", "AZ"]
    inputs = []
    for n in names:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        inputs.append(ci)
    custom.set_editor_property("inputs", inputs)

    pos = MEL.create_material_expression(m, unreal.MaterialExpressionPreSkinnedPosition, x, y)
    vc = MEL.create_material_expression(m, unreal.MaterialExpressionVertexColor, x, y + 120)
    MEL.connect_material_expressions(pos, "", custom, "P")
    MEL.connect_material_expressions(vc, "G", custom, "G")
    MEL.connect_material_expressions(vc, "B", custom, "Bw")
    MEL.connect_material_expressions(vc, "A", custom, "A")
    for i in range(4):
        d = MEL.create_material_expression(m, unreal.MaterialExpressionPerInstanceCustomData, x, y + 260 + i * 80)
        d.set_editor_property("data_index", i)
        MEL.connect_material_expressions(d, "", custom, "D%d" % i)
    t = MEL.create_material_expression(m, unreal.MaterialExpressionTime, x, y + 520)
    MEL.connect_material_expressions(t, "", custom, "T")
    r = MEL.create_material_expression(m, unreal.MaterialExpressionPerInstanceRandom, x, y + 600)
    MEL.connect_material_expressions(r, "", custom, "R")
    for i, (axis, vec) in enumerate((("AX", (1, 0, 0)), ("AY", (0, 1, 0)), ("AZ", (0, 0, 1)))):
        c3 = MEL.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, x - 300, y + 700 + i * 120)
        c3.set_editor_property("constant", unreal.LinearColor(vec[0], vec[1], vec[2], 1))
        tr = MEL.create_material_expression(m, unreal.MaterialExpressionTransform, x, y + 700 + i * 120)
        tr.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
        tr.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
        MEL.connect_material_expressions(c3, "", tr, "")
        MEL.connect_material_expressions(tr, "", custom, axis)
    MEL.connect_material_property(custom, "", MP.MP_WORLD_POSITION_OFFSET)


def build_materials(tex):
    m = new_material("M_Bumblebee_Body")
    bc = sample(m, tex["T_Bumblebee_Body_BC"], -700, -300)
    orm = sample(m, tex["T_Bumblebee_Body_ORM"], -700, 0, "masks")
    n = sample(m, tex["T_Bumblebee_Body_N"], -700, 300, "normal")
    MEL.connect_material_property(bc, "RGB", MP.MP_BASE_COLOR)
    MEL.connect_material_property(orm, "R", MP.MP_AMBIENT_OCCLUSION)
    MEL.connect_material_property(orm, "G", MP.MP_ROUGHNESS)
    MEL.connect_material_property(const(m, 0.6, -400, 150), "", MP.MP_SPECULAR)
    MEL.connect_material_property(n, "RGB", MP.MP_NORMAL)
    add_wpo(m)
    MEL.recompile_material(m)
    body = m

    m = new_material("M_Bumblebee_Fur")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    m.set_editor_property("opacity_mask_clip_value", 0.33)
    bc = sample(m, tex["T_Bumblebee_Fur_BC"], -800, -300)
    n = sample(m, tex["T_Bumblebee_Fur_N"], -800, 300, "normal")
    vc = MEL.create_material_expression(m, unreal.MaterialExpressionVertexColor, -800, 0)
    mul = MEL.create_material_expression(m, unreal.MaterialExpressionMultiply, -450, -250)
    MEL.connect_material_expressions(bc, "RGB", mul, "A")
    MEL.connect_material_expressions(vc, "R", mul, "B")
    MEL.connect_material_property(mul, "", MP.MP_BASE_COLOR)
    MEL.connect_material_property(bc, "A", MP.MP_OPACITY_MASK)
    MEL.connect_material_property(const(m, 0.5, -450, 100), "", MP.MP_ROUGHNESS)
    MEL.connect_material_property(const(m, 0.5, -450, 180), "", MP.MP_SPECULAR)
    MEL.connect_material_property(n, "RGB", MP.MP_NORMAL)
    add_wpo(m)
    MEL.recompile_material(m)
    fur = m

    m = new_material("M_Bumblebee_Wing")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("two_sided", True)
    m.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    for prop in ("output_translucent_velocity",):
        try:
            m.set_editor_property(prop, True)
        except Exception as e:
            warn(f"wing {prop}: {e}")
    bc = sample(m, tex["T_Bumblebee_Wing_BC"], -800, -300)
    fres = MEL.create_material_expression(m, unreal.MaterialExpressionFresnel, -800, 100)
    tint = MEL.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -800, 250)
    tint.set_editor_property("constant", unreal.LinearColor(0.10, 0.06, 0.16, 1.0))
    sheen = MEL.create_material_expression(m, unreal.MaterialExpressionMultiply, -500, 150)
    MEL.connect_material_expressions(fres, "", sheen, "A")
    MEL.connect_material_expressions(tint, "", sheen, "B")
    MEL.connect_material_property(bc, "RGB", MP.MP_BASE_COLOR)
    wop = MEL.create_material_expression(m, unreal.MaterialExpressionCustom, -350, -150)
    wop.set_editor_property("code", WING_OPACITY_HLSL)
    wop.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    wop.set_editor_property("description", "Wing blur opacity")
    wins = []
    for n in ("O", "D0", "D3"):
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        wins.append(ci)
    wop.set_editor_property("inputs", wins)
    MEL.connect_material_expressions(bc, "A", wop, "O")
    for i, n in ((0, "D0"), (3, "D3")):
        d = MEL.create_material_expression(m, unreal.MaterialExpressionPerInstanceCustomData, -650, -60 + i * 40)
        d.set_editor_property("data_index", i)
        MEL.connect_material_expressions(d, "", wop, n)
    MEL.connect_material_property(wop, "", MP.MP_OPACITY)
    MEL.connect_material_property(sheen, "", MP.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(const(m, 0.2, -500, 0), "", MP.MP_ROUGHNESS)
    MEL.connect_material_property(const(m, 0.7, -500, 60), "", MP.MP_SPECULAR)
    add_wpo(m)
    MEL.recompile_material(m)
    wing = m
    log("materials built")
    return {"Body": body, "Fur": fur, "Wing": wing}


def assign_by_slot(slots_owner, mats, is_skeletal):
    prop = "materials" if is_skeletal else "static_materials"
    slots = slots_owner.get_editor_property(prop)
    names = []
    for s in slots:
        nm = str(s.get_editor_property("material_slot_name"))
        names.append(nm)
        for key, mat in mats.items():
            if key.lower() in nm.lower():
                s.set_editor_property("material_interface", mat)
    slots_owner.set_editor_property(prop, slots)
    return names


# ----------------------------------------------------------------------------------------------- meshes
def import_skeletal(mats):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", True)
    ui.set_editor_property("create_physics_asset", False)
    sk = ui.get_editor_property("skeletal_mesh_import_data")
    sk.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    sk.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    sk.set_editor_property("import_morph_targets", False)
    sk.set_editor_property("convert_scene", True)
    an = ui.get_editor_property("anim_sequence_import_data")
    an.set_editor_property("animation_length", unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
    t = task(os.path.join(SRC, "SK_Bumblebee.fbx"), DEST, "SK_Bumblebee", ui)
    AT.import_asset_tasks([t])
    mesh = unreal.load_asset(DEST + "/SK_Bumblebee")
    if not isinstance(mesh, unreal.SkeletalMesh):
        report["errors"].append("skeletal mesh import failed: %s" % list(t.get_editor_property("imported_object_paths")))
        return
    report["skeletal_slots"] = assign_by_slot(mesh, mats, True)
    sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    for i in (1, 2):
        try:
            ok = sub.import_lod(mesh, i, os.path.join(SRC, f"SK_Bumblebee_LOD{i}.fbx"))
            log(f"skeletal LOD{i} -> {ok}")
        except Exception as e:
            warn(f"skeletal LOD{i}: {e}")
    try:
        infos = mesh.get_editor_property("lod_info")
        for i, size in enumerate((1.0, 0.25, 0.08)[:len(infos)]):
            infos[i].set_editor_property("screen_size", unreal.PerPlatformFloat(size))
        mesh.set_editor_property("lod_info", infos)
        report["skeletal_lods"] = len(infos)
    except Exception as e:
        warn(f"skeletal LOD screen sizes: {e}")
    report["anims"] = [str(p) for p in EAL.list_assets(DEST, recursive=False) if "Anim" in str(p) or "Fly" in str(p) or "Idle" in str(p)]


def import_static(name, mats):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", False)
    sm = ui.get_editor_property("static_mesh_import_data")
    sm.set_editor_property("combine_meshes", True)
    sm.set_editor_property("generate_lightmap_u_vs", False)
    sm.set_editor_property("auto_generate_collision", False)
    sm.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    sm.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    sm.set_editor_property("convert_scene", True)
    try:
        sm.set_editor_property("build_nanite", False)
    except Exception:
        pass
    t = task(os.path.join(STATIC, f"{name}_LOD0.fbx"), DEST, name, ui)
    AT.import_asset_tasks([t])
    mesh = unreal.load_asset(f"{DEST}/{name}")
    if not isinstance(mesh, unreal.StaticMesh):
        report["errors"].append(f"static import failed: {name}")
        return
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for i in (1, 2, 3):
        try:
            got = sub.import_lod(mesh, i, os.path.join(STATIC, f"{name}_LOD{i}.fbx"))
            if got != i:
                warn(f"{name} LOD{i} import returned {got}")
        except Exception as e:
            warn(f"{name} LOD{i}: {e}")
    # StaticMesh needs set_material(); editing the static_materials array copy does not stick
    slots = []
    for i, s in enumerate(mesh.get_editor_property("static_materials")):
        nm = str(s.get_editor_property("material_slot_name"))
        slots.append(nm)
        for key, mat in mats.items():
            if key.lower() in nm.lower():
                mesh.set_material(i, mat)
    applied = [s.get_editor_property("material_interface").get_name() for s in mesh.get_editor_property("static_materials")]
    # WPO lifts flapping wings above the bind-pose bounds
    mesh.set_editor_property("positive_bounds_extension", unreal.Vector(0.5, 0.5, 1.2))
    mesh.set_editor_property("negative_bounds_extension", unreal.Vector(0.5, 0.5, 0.6))
    info = {"slots": slots, "materials": applied, "lods": sub.get_lod_count(mesh), "verts": [sub.get_number_verts(mesh, i) for i in range(sub.get_lod_count(mesh))]}
    try:
        info["vertex_colors"] = bool(sub.has_vertex_colors(mesh))
    except Exception as e:
        info["vertex_colors"] = str(e)
    b = mesh.get_bounding_box()
    info["bounds"] = [round(v, 3) for v in (b.min.x, b.min.y, b.min.z, b.max.x, b.max.y, b.max.z)]
    report[name] = info
    log(f"{name}: {info}")


try:
    tex = import_textures()
    mats = build_materials(tex)
    import_skeletal(mats)
    import_static("SM_Bumblebee_Fly", mats)
    import_static("SM_Bumblebee_Landed", mats)
    saved = EAL.save_directory(DEST, only_if_is_dirty=False, recursive=True)
    report["saved"] = bool(saved)
    report["assets"] = [str(p) for p in EAL.list_assets(DEST, recursive=True)]
except Exception as e:
    import traceback
    report["errors"].append(traceback.format_exc())
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=1)
log("report -> " + REPORT)
if "-BeeSetupQuit" in unreal.SystemLibrary.get_command_line():
    unreal.SystemLibrary.quit_editor()
