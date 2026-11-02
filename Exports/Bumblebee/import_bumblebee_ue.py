"""Import the bumblebee into Unreal Engine 5.7 and build its materials.

Run from the Unreal editor:  Tools > Execute Python Script...  (or `py "<path>/import_bumblebee_ue.py"` in the Cmd console)
Edit DEST below if you want it somewhere else. Safe to re-run (assets are replaced).
"""
import os
import unreal

SRC = os.path.dirname(os.path.abspath(__file__))
DEST = "/Game/Prophecy/Creatures/Bumblebee"

AT = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary


def log(msg):
    unreal.log("[Bumblebee] " + msg)


# ----------------------------------------------------------------------------- textures
def import_textures():
    names = ["T_Bumblebee_Body_BC", "T_Bumblebee_Body_N", "T_Bumblebee_Body_ORM",
             "T_Bumblebee_Fur_BC", "T_Bumblebee_Fur_N", "T_Bumblebee_Wing_BC"]
    tasks = []
    for n in names:
        t = unreal.AssetImportTask()
        t.filename = os.path.join(SRC, n + ".png")
        t.destination_path = DEST + "/Textures"
        t.destination_name = n
        t.replace_existing = True
        t.automated = True
        t.save = False
        tasks.append(t)
    AT.import_asset_tasks(tasks)
    tex = {}
    for n in names:
        a = unreal.load_asset(f"{DEST}/Textures/{n}")
        if n.endswith("_N"):
            a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            a.set_editor_property("srgb", False)
            a.set_editor_property("flip_green_channel", False)   # files are already DirectX (green down)
        elif n.endswith("_ORM"):
            a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
            a.set_editor_property("srgb", False)
        a.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_CHARACTER)
        tex[n] = a
    log("textures imported")
    return tex


# ----------------------------------------------------------------------------- materials
def new_material(name):
    path = f"{DEST}/Materials/{name}"
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    return AT.create_asset(name, DEST + "/Materials", unreal.Material, unreal.MaterialFactoryNew())


def sample(mat, texture, x, y, normal=False, masks=False):
    s = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, x, y)
    s.set_editor_property("texture", texture)
    if normal:
        s.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    elif masks:
        s.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    return s


def const(mat, v, x, y):
    c = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, x, y)
    c.set_editor_property("r", v)
    return c


def build_materials(tex):
    MP = unreal.MaterialProperty

    # Body: opaque chitin / skin
    m = new_material("M_Bumblebee_Body")
    bc = sample(m, tex["T_Bumblebee_Body_BC"], -600, -200)
    orm = sample(m, tex["T_Bumblebee_Body_ORM"], -600, 100, masks=True)
    n = sample(m, tex["T_Bumblebee_Body_N"], -600, 400, normal=True)
    MEL.connect_material_property(bc, "RGB", MP.MP_BASE_COLOR)
    MEL.connect_material_property(orm, "R", MP.MP_AMBIENT_OCCLUSION)
    MEL.connect_material_property(orm, "G", MP.MP_ROUGHNESS)
    MEL.connect_material_property(const(m, 0.6, -300, 250), "", MP.MP_SPECULAR)
    MEL.connect_material_property(n, "RGB", MP.MP_NORMAL)
    MEL.recompile_material(m)
    body = m

    # Fur cards: masked, one-sided (cards are modelled back-to-back with outward normals).
    # Vertex colour R = baked fur self-shadowing (dark at roots / underside).
    m = new_material("M_Bumblebee_Fur")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    m.set_editor_property("opacity_mask_clip_value", 0.33)
    m.set_editor_property("dithered_lod_transition", True)
    bc = sample(m, tex["T_Bumblebee_Fur_BC"], -700, -200)
    n = sample(m, tex["T_Bumblebee_Fur_N"], -700, 400, normal=True)
    vc = MEL.create_material_expression(m, unreal.MaterialExpressionVertexColor, -700, 100)
    mul = MEL.create_material_expression(m, unreal.MaterialExpressionMultiply, -350, -150)
    MEL.connect_material_expressions(bc, "RGB", mul, "A")
    MEL.connect_material_expressions(vc, "R", mul, "B")
    MEL.connect_material_property(mul, "", MP.MP_BASE_COLOR)
    MEL.connect_material_property(bc, "A", MP.MP_OPACITY_MASK)
    MEL.connect_material_property(const(m, 0.5, -350, 150), "", MP.MP_ROUGHNESS)
    MEL.connect_material_property(const(m, 0.5, -350, 250), "", MP.MP_SPECULAR)
    MEL.connect_material_property(n, "RGB", MP.MP_NORMAL)
    MEL.recompile_material(m)
    fur = m

    # Wings: translucent, two-sided, lit per pixel, with a faint thin-film sheen at grazing angles
    m = new_material("M_Bumblebee_Wing")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("two_sided", True)
    m.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    bc = sample(m, tex["T_Bumblebee_Wing_BC"], -700, -200)
    fres = MEL.create_material_expression(m, unreal.MaterialExpressionFresnel, -700, 250)
    tint = MEL.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -700, 400)
    tint.set_editor_property("constant", unreal.LinearColor(0.10, 0.06, 0.16, 1.0))
    sheen = MEL.create_material_expression(m, unreal.MaterialExpressionMultiply, -400, 300)
    MEL.connect_material_expressions(fres, "", sheen, "A")
    MEL.connect_material_expressions(tint, "", sheen, "B")
    MEL.connect_material_property(bc, "RGB", MP.MP_BASE_COLOR)
    MEL.connect_material_property(bc, "A", MP.MP_OPACITY)
    MEL.connect_material_property(sheen, "", MP.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(const(m, 0.2, -400, 100), "", MP.MP_ROUGHNESS)
    MEL.connect_material_property(const(m, 0.7, -400, 180), "", MP.MP_SPECULAR)
    MEL.recompile_material(m)
    wing = m
    log("materials built")
    return {"Body": body, "Fur": fur, "Wing": wing}


# ----------------------------------------------------------------------------- mesh + anims
def import_mesh():
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
    t = unreal.AssetImportTask()
    t.filename = os.path.join(SRC, "SK_Bumblebee.fbx")
    t.destination_path = DEST
    t.destination_name = "SK_Bumblebee"
    t.replace_existing = True
    t.automated = True
    t.save = False
    t.options = ui
    AT.import_asset_tasks([t])
    log("imported: " + ", ".join(t.get_editor_property("imported_object_paths")))
    for p in EAL.list_assets(DEST, recursive=False):
        a = unreal.load_asset(p)
        if isinstance(a, unreal.SkeletalMesh):
            return a
    raise RuntimeError("Skeletal mesh not found after import - check the Output Log")


def assign_materials(mesh, mats):
    slots = mesh.get_editor_property("materials")
    for s in slots:
        name = str(s.get_editor_property("material_slot_name"))
        for key, mat in mats.items():
            if key.lower() in name.lower():
                s.set_editor_property("material_interface", mat)
    mesh.set_editor_property("materials", slots)
    log("materials assigned to slots: " + ", ".join(str(s.get_editor_property("material_slot_name")) for s in slots))


def import_lods(mesh):
    sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    for i in (1, 2):
        f = os.path.join(SRC, f"SK_Bumblebee_LOD{i}.fbx")
        try:
            sub.import_lod(mesh, i, f)
            log(f"LOD{i} imported")
        except Exception as e:   # older/newer API differences: fall back to manual import
            unreal.log_warning(f"[Bumblebee] LOD{i} auto-import failed ({e}). Import it from the mesh editor: LOD Settings > LOD Import.")
    # screen sizes: hero detail close up, cheap far away
    try:
        infos = mesh.get_editor_property("lod_info")
        for i, size in enumerate((1.0, 0.25, 0.08)[:len(infos)]):
            infos[i].set_editor_property("screen_size", unreal.PerPlatformFloat(size))
        mesh.set_editor_property("lod_info", infos)
    except Exception as e:
        unreal.log_warning(f"[Bumblebee] could not set LOD screen sizes: {e}")


tex = import_textures()
mats = build_materials(tex)
mesh = import_mesh()
assign_materials(mesh, mats)
import_lods(mesh)
EAL.save_directory(DEST, only_if_is_dirty=True, recursive=True)
log("done -> " + DEST)
