"""Run ONLY with BloodDecalLab.uproject, never the user's Prophecy editor."""
import json
import pathlib
import random
import time
import unreal

assert pathlib.Path(unreal.Paths.get_project_file_path()).stem == "BloodDecalLab"
OUT = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "Results"
OUT.mkdir(parents=True, exist_ok=True)
REPORT = {"scope": "isolated Unreal scene; no production assets loaded", "checks": []}
LAYOUT = {}

def require(condition, name):
    REPORT["checks"].append({"name": name, "passed": bool(condition)})
    if not condition:
        raise AssertionError(name)

def drain(a):
    a.process_changes()
    iterations = 0
    while a.has_pending_changes():
        a.process_changes()
        iterations += 1
        require(iterations < 4096, "queued work eventually completes")

def material(name, color, decal=False):
    path = "/Game/Lab/" + name
    m = unreal.load_asset(path)
    if not m:
        m = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, "/Game/Lab", unreal.Material, unreal.MaterialFactoryNew())
        if decal:
            m.set_editor_property("material_domain", unreal.MaterialDomain.MD_DEFERRED_DECAL)
            m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        rgb = unreal.MaterialEditingLibrary.create_material_expression(m, unreal.MaterialExpressionConstant3Vector)
        rgb.set_editor_property("constant", unreal.LinearColor(*color, 1))
        unreal.MaterialEditingLibrary.connect_material_property(rgb, "", unreal.MaterialProperty.MP_BASE_COLOR)
        value = unreal.MaterialEditingLibrary.create_material_expression(m, unreal.MaterialExpressionConstant)
        value.set_editor_property("r", 1.0)
        unreal.MaterialEditingLibrary.connect_material_property(value, "", unreal.MaterialProperty.MP_OPACITY if decal else unreal.MaterialProperty.MP_ROUGHNESS)
        unreal.MaterialEditingLibrary.recompile_material(m)
        unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m

def actor(cls, xyz, rotation=None):
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        cls, unreal.Vector(*xyz), rotation or unreal.Rotator())

def grid(label, xyz, shape="filled", legacy=False):
    a = actor(unreal.BloodMergeScene, xyz)
    a.set_actor_label(label)
    a.set_editor_property("decal_material", BLOOD)
    a.set_editor_property("pattern", shape)
    a.set_editor_property("legacy_comparison", legacy)
    return a

def cells_from_decals(a):
    seen = set()
    overlap = False
    for d in a.get_components_by_class(unreal.DecalComponent):
        if not d.is_visible():
            continue
        p = d.get_editor_property("relative_location")
        size = d.get_editor_property("decal_size")
        cell = a.get_editor_property("cell_size")
        w, h = round(2 * size.z / cell), round(2 * size.y / cell)
        x, y = round(p.x / cell - w / 2), round(p.y / cell - h / 2)
        for yy in range(y, y+h):
            for xx in range(x, x+w):
                if (xx, yy) in seen:
                    overlap = True
                seen.add((xx, yy))
        require(abs((p.z-size.x)+1) < 0.001, "projection reaches floor")
    return seen, overlap

def footprints(a):
    rectangles = []
    for d in a.get_components_by_class(unreal.DecalComponent):
        if d.is_visible():
            p = d.get_editor_property("relative_location")
            size = d.get_editor_property("decal_size")
            rectangles.append([p.x-size.z, p.y-size.y, 2*size.z, 2*size.y])
    return rectangles

try:
    WORLD = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    require(WORLD is not None, "fresh isolated test world")
    BLOOD = material("M_Blood", (0.22, 0.002, 0.001), True)
    FLOOR = material("M_Floor", (0.55, 0.55, 0.55))
    floor = actor(unreal.StaticMeshActor, (275, 450, -5))
    floor.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
    floor.static_mesh_component.set_material(0, FLOOR)
    floor.set_actor_scale3d(unreal.Vector(8, 14, .1))
    sun = actor(unreal.DirectionalLight, (0, 0, 600), unreal.Rotator(pitch=-65, yaw=-30))
    sun.light_component.set_editor_property("intensity", 5.0)

    pairs = []
    for i, shape in enumerate(["filled", "hole", "splash", "strip"]):
        old = grid("OLD_" + shape, (0, i*300, 0), shape, True)
        new = grid("NEW_" + shape, (350, i*300, 0), shape)
        pairs.append((old, new, shape))

    spray = grid("NEW_ContinuousSpray", (800, 0, 0), "splash")
    spray.set_editor_property("spray", True)
    spray_floor = actor(unreal.StaticMeshActor, (900, 100, -5))
    spray_floor.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
    spray_floor.static_mesh_component.set_material(0, FLOOR)
    spray_floor.set_actor_scale3d(unreal.Vector(4,4,.1))
    start = actor(unreal.PlayerStart, (275,-300,250), unreal.Rotator(pitch=-25,yaw=90))
    require(unreal.EditorLoadingAndSavingUtils.save_map(WORLD, "/Game/Maps/BloodMergeLab"),
            "isolated scene saved")

    REPORT["kernel"] = json.loads(pairs[0][1].validate())
    require(REPORT["kernel"]["failures"] == 0, "4005 kernel coverage cases and negative coordinate checks")
    REPORT["benchmark"] = json.loads(pairs[0][1].benchmark())
    REPORT["patterns"] = []
    for old, new, shape in pairs:
        old.populate(shape)
        new.populate(shape)
        REPORT["patterns"].append({
            "shape": shape,
            "old_decals": old.get_editor_property("active_decals"),
            "new_decals": new.get_editor_property("active_decals"),
            "occupied_cells": new.get_editor_property("occupied_cells"),
            "last_update_ms": new.get_editor_property("last_update_ms")
        })
        LAYOUT[shape] = {"old": footprints(old), "new": footprints(new)}
        got, overlap = cells_from_decals(new)
        require(not overlap and len(got) == new.get_editor_property("occupied_cells"), shape + " actual decal coverage and no overlap")
        if shape == "filled":
            require(got == {(x,y) for x in range(16) for y in range(16)}, "filled region exact")
            require(new.get_editor_property("active_decals") == 1, "filled region one rectangle")
        if shape == "hole":
            require(got == {(x,y) for x in range(16) for y in range(16) if not (5 <= x < 11 and 5 <= y < 11)}, "hole remains empty")

    probe = grid("TransientValidation", (3000,3000,0))
    expected = set()
    rng = random.Random(71)
    elapsed = []
    for batch in range(50):
        for _ in range(40):
            p = (rng.randrange(-40,40), rng.randrange(-40,40))
            probe.add_cell(*p)
            expected.add(p)
        for _ in range(16): # bounded region count in this fixture
            was_pending = probe.has_pending_changes()
            before_created = probe.get_editor_property("created_components")
            probe.process_changes()
            require(probe.get_editor_property("created_components")-before_created <= 16,
                    "streaming also respects allocation cap")
            if was_pending:
                elapsed.append(probe.get_editor_property("last_update_ms"))
    got, overlap = cells_from_decals(probe)
    require(got == expected and not overlap, "streamed additions across positive/negative chunk boundaries")
    before = probe.get_editor_property("rebuilds")
    created = probe.get_editor_property("created_components")
    for p in expected:
        require(not probe.add_cell(*p), "repeated hit does not dirty a region")
    probe.process_changes()
    require(probe.get_editor_property("rebuilds") == before, "no rebuild after repeated hits")
    require(probe.get_editor_property("created_components") == created, "no component allocation after repeated hits")
    elapsed.sort()
    REPORT["stream"] = {"cells":len(expected),"rectangles":probe.get_editor_property("active_decals"),
                        "update_max_ms":max(elapsed),"update_p95_ms":elapsed[int(len(elapsed)*.95)],
                        "measured_updates":len(elapsed),
                        "scope":"non-idle synchronous CPU component updates; not GPU timing; competing user workloads"}
    probe.clear()
    require(probe.get_editor_property("active_decals") == 0, "clear retires components")
    probe.set_editor_property("max_decals", 4)
    for y in range(8):
        for x in range(8):
            if (x+y)%2 == 0:
                probe.add_cell(x,y)
    probe.process_changes()
    require(probe.get_editor_property("capacity_blocked"), "decal limit is explicit rather than allocating without a bound")
    count = probe.get_editor_property("created_components")
    for _ in range(10):
        probe.process_changes()
    require(probe.get_editor_property("created_components") == count, "blocked capacity does not retry allocations")
    probe.set_editor_property("max_decals", 4096)
    drain(probe)
    require(not probe.get_editor_property("capacity_blocked") and probe.get_editor_property("active_decals")==32, "raising capacity resumes exact pending partition")
    before = probe.get_editor_property("created_components")
    for y in range(8):
        for x in range(8):
            probe.add_cell(x,y)
    probe.process_changes()
    require(probe.get_editor_property("active_decals")==1, "filled checkerboard retiled to one")
    require(probe.get_editor_property("created_components")==before, "retile reuses existing components")
    probe.clear()
    staged_cells = {(x,y) for x in range(32) for y in range(32) if (x+y)%2==0}
    for p in staged_cells:
        probe.add_cell(*p)
    probe.process_changes()
    require(probe.get_editor_property("created_components")<=16, "cold sparse patch bounds allocations per update")
    require(probe.get_editor_property("active_decals")==0 and probe.has_pending_changes(),
            "unfinished cold region stays queued")
    require(not footprints(probe), "prepared components remain hidden until complete")
    probe.add_cell(1,0)
    staged_cells.add((1,0))
    drain(probe)
    got, overlap = cells_from_decals(probe)
    require(got==staged_cells and not overlap, "new hits during preparation are retained with exact final coverage")
    probe.clear()
    require(probe.add_stain(unreal.Vector(3031.25, 2993.75, 0), 0) == 1,
            "world impact maps through receiver transform")
    require(probe.add_stain(unreal.Vector(3031.25, 2993.75, 20), 0) == 0,
            "another plane is rejected")
    probe.process_changes()
    got, overlap = cells_from_decals(probe)
    require(got == {(2,-1)} and not overlap, "world impact produces exact translated negative cell")
    probe.clear()
    probe.add_stain(unreal.Vector(3000, 3000, 0), 10)
    for _ in range(4):
        probe.process_changes()
    expected_radius = {(x,y) for x in range(-3,4) for y in range(-3,4)
                       if ((x+.5)*12.5)**2 + ((y+.5)*12.5)**2 <= (10+12.5*.7072)**2}
    got, overlap = cells_from_decals(probe)
    require(got == expected_radius and not overlap, "radius impact covers the intended cells across four regions")
    probe.clear()
    unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(probe)
    spray.populate("splash")

    REPORT["rendered"] = False
    if "-nullrhi" not in unreal.SystemLibrary.get_command_line().lower():
        # Render the actual Unreal decal scene, not a schematic.
        cap = actor(unreal.SceneCapture2D, (275,550,1400), unreal.Rotator(pitch=-90,yaw=-90))
        cc = cap.get_component_by_class(unreal.SceneCaptureComponent2D)
        cc.set_editor_property("capture_every_frame", False)
        cc.set_editor_property("capture_on_movement", False)
        cc.set_editor_property("projection_type", unreal.CameraProjectionMode.ORTHOGRAPHIC)
        cc.set_editor_property("ortho_width", 1350)
        cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        rt = unreal.RenderingLibrary.create_render_target2d(WORLD, 1100, 1100, unreal.TextureRenderTargetFormat.RTF_RGBA8)
        cc.set_editor_property("texture_target", rt)
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        for _ in range(3):
            cc.capture_scene()
        unreal.RenderingLibrary.export_render_target(WORLD, rt, str(OUT), "comparison.png")
        REPORT["rendered"] = True
    REPORT["success"] = True
except Exception:
    import traceback
    REPORT["success"] = False
    REPORT["error"] = traceback.format_exc()
finally:
    # Aggregate repetitive assertions instead of retaining thousands of lines.
    checks = REPORT.pop("checks")
    REPORT["passed_checks"] = sum(c["passed"] for c in checks)
    REPORT["failed_checks"] = [c for c in checks if not c["passed"]]
    (OUT / "validation.json").write_text(json.dumps(REPORT,indent=2))
    (OUT / "footprints.json").write_text(json.dumps(LAYOUT,separators=(",",":")))
    print(json.dumps(REPORT))
if not REPORT["success"]:
    raise RuntimeError(REPORT["error"])
