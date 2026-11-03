"""Overlay the global wind bursts on the forest foliage, without touching the originals' graphs.
 For each foliage master used by the PCG forest (MA_Foliage_Trees, M_MS_Foliage, M_MS_Billboard):
   duplicate -> /Game/Prophecy/Ambient/Wind/Masters/<name>_Wind<version>, WPO = original WPO + MF_WindBurst(Height, Stiffness, Flutter)
 then reparent the forest's material instances onto the duplicates and set their per-plant wind values.
 Revert: Exports/Wind/wind_overlay_revert.py (reads Saved/WindTest/overlay_revert.json).
Run in the open editor: Tools/RunUnrealRemote.py Exports/Wind/wind_overlay.py"""
import os, json
import unreal

DEST = "/Game/Prophecy/Ambient/Wind/Masters"
MF_PATH = "/Game/Prophecy/Ambient/Wind/MF_WindBurst"
OUT = os.path.join(unreal.Paths.project_saved_dir(), "WindTest")
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary
MP = unreal.MaterialProperty
rep = {"errors": [], "masters": {}, "instances": {}}

# master -> (duplicate name, Nanite / bounds max WPO displacement cm). The duplicates are versioned: a rebuild makes new
# ones, moves the instances onto them, then deletes the old ones (never deletes a master an instance still uses).
VERSION = 4
MASTERS = {
    "/ProceduralVegetationEditor/SampleAssets/Materials/MasterMaterials/MA_Foliage_Trees": (f"MA_Foliage_Trees_Wind{VERSION}", 300.0),
    "/Fab/Materials/Standard/M_MS_Foliage": (f"M_MS_Foliage_Wind{VERSION}", 60.0),
    "/Fab/Materials/Standard/M_MS_Billboard": (f"M_MS_Billboard_Wind{VERSION}", 60.0),
}
# what the instances are drawn with (PCG / foliage / plain meshes, Nanite or not): set explicitly, a cooked or
# standalone game cannot add a missing usage and falls back to the default material
USAGES = ["MATUSAGE_NANITE", "MATUSAGE_INSTANCED_STATIC_MESHES", "MATUSAGE_STATIC_LIGHTING"]
# instance -> (Height cm in local units, Stiffness 0 grass .. 1 trunk, Flutter cm, Branch 0..1, natural frequency Hz)
MEGA = "/Game/Fab/Megascans/Plants"
INSTANCES = {
    "/Game/Megaplant_Library/Tree_Hornbeam/Materials/MI_Tree_Hornbeam_01_Bark": (1500, 0.92, 0.0, 1.0, 0.3),
    "/Game/Megaplant_Library/Tree_Hornbeam/Materials/MI_Tree_Hornbeam_01_Foliage": (1500, 0.92, 4.0, 1.0, 0.3),
    f"{MEGA}/Wild_Grass_vlkhcbxia/High/vlkhcbxia_tier_1/Materials/MI_vlkhcbxia": (38, 0.12, 0.8, 0.0, 1.6),
    f"{MEGA}/Wild_Grass_vlkhcbxia/High/vlkhcbxia_tier_1/Materials/MI_vlkhcbxia_Billboard": (38, 0.12, 0.0, 0.0, 1.6),
    f"{MEGA}/Thatching_Grass_uddmcgbia/Medium/uddmcgbia_tier_2/Materials/MI_uddmcgbia": (60, 0.18, 1.0, 0.0, 1.2),
    f"{MEGA}/Thatching_Grass_uddmcgbia/Medium/uddmcgbia_tier_2/Materials/MI_uddmcgbia_Billboard": (60, 0.18, 0.0, 0.0, 1.2),
    f"{MEGA}/Violet_Wood_Sorrel_uchkajuia/Medium/uchkajuia_tier_2/Materials/MI_uchkajuia": (20, 0.35, 0.8, 0.0, 2.2),
    f"{MEGA}/Violet_Wood_Sorrel_uchkajuia/Medium/uchkajuia_tier_2/Materials/MI_uchkajuia_Billboard": (20, 0.35, 0.0, 0.0, 2.2),
    f"{MEGA}/Matted_Pratia_uegjcflia/Medium/uegjcflia_tier_2/Materials/MI_uegjcflia": (8, 0.55, 0.4, 0.0, 2.8),
    f"{MEGA}/Matted_Pratia_uegjcflia/Medium/uegjcflia_tier_2/Materials/MI_uegjcflia_Billboard": (8, 0.55, 0.0, 0.0, 2.8),
}
ATTRS = ["BaseColor", "Metallic", "Specular", "Roughness", "Anisotropy", "EmissiveColor", "Opacity", "OpacityMask", "Normal", "Tangent",
         "SubsurfaceColor", "ClearCoat", "ClearCoatRoughness", "AmbientOcclusion", "Refraction",
         "CustomizedUV0", "CustomizedUV1", "CustomizedUV2", "CustomizedUV3", "CustomizedUV4", "CustomizedUV5", "CustomizedUV6", "CustomizedUV7",
         "PixelDepthOffset", "ShadingModel", "SurfaceThickness", "Displacement", "FrontMaterial"]


def out_name(m, prop):
    try: return MEL.get_material_property_input_node_output_name(m, prop) or ""
    except Exception: return ""


def scalar(m, name, default, x, y):
    p = MEL.create_material_expression(m, unreal.MaterialExpressionScalarParameter, x, y)
    p.set_editor_property("parameter_name", name)
    p.set_editor_property("default_value", default)
    p.set_editor_property("group", "Wind Burst")
    return p


def stats(m):
    try:
        s = MEL.get_statistics(m)
        return {"vs": s.num_vertex_shader_instructions, "ps": s.num_pixel_shader_instructions, "samplers": s.num_samplers}
    except Exception as e:
        return {"err": str(e)}


def overlay(src_path, dst_name, max_disp, mf):
    src = unreal.load_asset(src_path)
    dst_path = f"{DEST}/{dst_name}"
    if EAL.does_asset_exist(dst_path):
        EAL.delete_asset(dst_path)
    m = EAL.duplicate_asset(src_path, dst_path)
    r = {"src": src_path, "dst": dst_path, "connected": []}
    call = MEL.create_material_expression(m, unreal.MaterialExpressionMaterialFunctionCall, -2400, 2400)
    call.set_editor_property("material_function", mf)
    for i, (n, d) in enumerate((("Height", 100.0), ("Stiffness", 0.5), ("Flutter", 0.0), ("Branch", 0.0), ("Freq", 1.0))):
        MEL.connect_material_expressions(scalar(m, "WindBurst" + n, d, -2800, 2300 + i * 120), "", call, n)
    add = MEL.create_material_expression(m, unreal.MaterialExpressionAdd, -2000, 2300)
    MEL.connect_material_expressions(call, "WPO", add, "B")
    if m.get_editor_property("use_material_attributes"):
        root = MEL.get_material_property_input_node(m, MP.MP_MATERIAL_ATTRIBUTES)
        if not root:
            raise RuntimeError("no material attributes input")
        brk = MEL.create_material_expression(m, unreal.MaterialExpressionBreakMaterialAttributes, -1700, 1800)
        mk = MEL.create_material_expression(m, unreal.MaterialExpressionMakeMaterialAttributes, -1300, 1800)
        on = out_name(m, MP.MP_MATERIAL_ATTRIBUTES)
        r["brk_in"] = next((n for n in ("", "MaterialAttributes", "Attr") if MEL.connect_material_expressions(root, on, brk, n)), None)
        if r["brk_in"] is None:
            raise RuntimeError("could not wire Break Material Attributes")
        for a in ATTRS:
            if MEL.connect_material_expressions(brk, a, mk, a): r["connected"].append(a)
        ok_wpo = MEL.connect_material_expressions(brk, "WorldPositionOffset", add, "A")
        ok_wpo = MEL.connect_material_expressions(add, "", mk, "WorldPositionOffset") and ok_wpo
        r["wpo_wired"] = bool(ok_wpo)
        MEL.connect_material_property(mk, "", MP.MP_MATERIAL_ATTRIBUTES)
    else:
        root = MEL.get_material_property_input_node(m, MP.MP_WORLD_POSITION_OFFSET)
        if root:
            MEL.connect_material_expressions(root, out_name(m, MP.MP_WORLD_POSITION_OFFSET), add, "A")
        r["wpo_wired"] = bool(MEL.connect_material_property(add, "", MP.MP_WORLD_POSITION_OFFSET))
    m.set_editor_property("max_world_position_offset_displacement", max_disp)
    r["usages"] = []
    for u in USAGES:
        try:
            MEL.set_material_usage(m, getattr(unreal.MaterialUsage, u))
            r["usages"].append(u)
        except Exception as e:
            r.setdefault("usage_errors", []).append(f"{u}: {e}")
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m, only_if_is_dirty=False)
    r["src_stats"] = stats(src)
    return m, r


try:
    mf = unreal.load_asset(MF_PATH)
    if not mf:
        raise RuntimeError("MF_WindBurst missing - run setup_wind.py first")
    revert_path = os.path.join(OUT, "overlay_revert.json")
    revert = json.load(open(revert_path)) if os.path.exists(revert_path) else {}
    new = {}
    import sys
    only_instances = "--instances-only" in sys.argv
    for src, (name, md) in MASTERS.items():
        if only_instances and EAL.does_asset_exist(f"{DEST}/{name}"):
            new[src.split("/")[-1]] = unreal.load_asset(f"{DEST}/{name}")
            continue
        try:
            m, r = overlay(src, name, md, mf)
            new[src.split("/")[-1]] = m
            rep["masters"][name] = r
        except Exception:
            import traceback
            rep["errors"].append(f"{name}: " + traceback.format_exc())
    for mi_path, (h, st, fl, br, fq) in INSTANCES.items():
        mi = unreal.load_asset(mi_path)
        if not mi:
            rep["errors"].append("missing " + mi_path); continue
        parent = mi.get_editor_property("parent")
        base = parent
        while isinstance(base, unreal.MaterialInstance) and base.get_editor_property("parent"):
            base = base.get_editor_property("parent")
        if base is None and mi_path not in revert:
            rep["errors"].append(f"{mi_path}: no parent and no revert record"); continue
        key = (base.get_path_name() if base else revert[mi_path]).split(".")[0].split("/")[-1].split("_Wind")[0]
        if key not in new:
            rep["errors"].append(f"{mi_path}: master {key} not overlaid"); continue
        if mi_path not in revert:
            revert[mi_path] = parent.get_path_name()		# the first, original parent
        if parent is None or (parent != new[key] and base != new[key]):
            MEL.set_material_instance_parent(mi, new[key])
        MEL.set_material_instance_scalar_parameter_value(mi, "WindBurstHeight", float(h))
        MEL.set_material_instance_scalar_parameter_value(mi, "WindBurstStiffness", float(st))
        MEL.set_material_instance_scalar_parameter_value(mi, "WindBurstFlutter", float(fl))
        MEL.set_material_instance_scalar_parameter_value(mi, "WindBurstBranch", float(br))
        MEL.set_material_instance_scalar_parameter_value(mi, "WindBurstFreq", float(fq))
        MEL.update_material_instance(mi)
        EAL.save_loaded_asset(mi, only_if_is_dirty=False)
        rep["instances"][mi_path] = {"parent": mi.get_editor_property("parent").get_path_name(), "was": revert[mi_path], "h": h, "stiff": st, "flutter": fl, "branch": br, "freq": fq}
    os.makedirs(OUT, exist_ok=True)
    json.dump(revert, open(revert_path, "w"), indent=1)
    # retire the previous versions once nothing points at them any more
    keep = {f"{DEST}/{n}" for n, _ in MASTERS.values()}
    rep["deleted"] = []
    if not rep["errors"]:
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        for p in EAL.list_assets(DEST, recursive=False):
            pkg = str(p).split(".")[0]
            if pkg in keep:
                continue
            refs = [str(x) for x in (ar.get_referencers(pkg, unreal.AssetRegistryDependencyOptions(True, True, True, True, True)) or []) if not str(x).startswith(DEST)]
            # the registry still lists the instances we just moved (until it rescans): check them in memory instead
            moved = set(INSTANCES.keys())
            refs = [r for r in refs if r not in moved]
            if refs:
                rep.setdefault("kept_old", {})[pkg] = refs[:5]
            elif EAL.delete_asset(pkg):
                rep["deleted"].append(pkg)
except Exception:
    import traceback
    rep["errors"].append(traceback.format_exc())
json.dump(rep, open(os.path.join(OUT, "overlay.json"), "w"), indent=1)
unreal.log("WINDOVERLAY errors=%d" % len(rep["errors"]))
