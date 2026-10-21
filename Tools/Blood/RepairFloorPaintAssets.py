"""Repair the experiment floor's paint UVs and preserving material pair."""
import hashlib, json, pathlib, shutil, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
assert ed.get_editor_world().get_path_name() == "/Game/explosionVFX.explosionVFX"
root = pathlib.Path(unreal.Paths.project_dir()).resolve()
out = root / "Saved/Diagnostics/FloorPaintFix"
out.mkdir(parents=True, exist_ok=True)
actors = unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(), unreal.Actor)
manager = next(a for a in actors if a.get_class().get_name().startswith("A_DecalManager_C"))
floor = manager.get_editor_property("floor")
paint = manager.get_editor_property("paint manager")
component = floor.get_component_by_class(unreal.StaticMeshComponent)
source_mesh = unreal.load_asset("/Engine/MapTemplates/SM_Template_Map_Floor")
clean = unreal.load_asset("/Engine/OpenWorldTemplate/LandscapeMaterial/MI_ProcGrid")
parent_path = "/Game/Prophecy/BloodTexturePainting/Generated/_Engine_OpenWorldTemplate_LandscapeMaterial_M_ProcGrid_BloodPaint"
blood_parent = unreal.load_asset(parent_path)
assert blood_parent and component.static_mesh == source_mesh
assert component.get_material(0) == clean
bp = unreal.load_asset("/Game/_mygame/blood2/A_DecalManager")

# Preserve the user's current map and graph edits before changing anything.
for rel in ["Content/explosionVFX.umap", "Content/_mygame/blood2/A_DecalManager.uasset"]:
    p = root / rel
    dst = out / (p.stem + ".before" + p.suffix)
    if p.exists() and not dst.exists(): shutil.copy2(p, dst)
packages = [ed.get_editor_world().get_outermost(), bp.get_outermost()]
assert unreal.EditorLoadingAndSavingUtils.save_packages(packages, True)

mesh_path = "/Game/Prophecy/BloodTexturePainting/SM_ExperimentFloor_PaintUV"
assert not unreal.EditorAssetLibrary.does_asset_exist(mesh_path), "Existing prepared mesh; inspect before retry"
mesh = unreal.EditorAssetLibrary.duplicate_asset(source_mesh.get_path_name().split(".")[0], mesh_path)
assert mesh
box = mesh.get_bounding_box()
center = (box.min + box.max) * 0.5
size = box.max - box.min
sme = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
for lod in range(sme.get_lod_count(mesh)):
    assert sme.generate_box_uv_channel(mesh, lod, 0, center, unreal.Rotator(), size)
assert unreal.EditorAssetLibrary.save_loaded_asset(mesh)

mi_path = "/Game/Prophecy/BloodTexturePainting/Generated/_Engine_OpenWorldTemplate_LandscapeMaterial_MI_ProcGrid_BloodPaint"
blood = unreal.load_asset(mi_path)
if not blood:
    blood = unreal.EditorAssetLibrary.duplicate_asset(clean.get_path_name().split(".")[0], mi_path)
assert isinstance(blood, unreal.MaterialInstanceConstant)
# Copy every instance override, including the static switches driving the grid.
for prop in ["scalar_parameter_values", "vector_parameter_values", "texture_parameter_values",
             "base_property_overrides"]:
    blood.set_editor_property(prop, clean.get_editor_property(prop))
unreal.MaterialEditingLibrary.set_material_instance_parent(blood, blood_parent)
for name in unreal.MaterialEditingLibrary.get_static_switch_parameter_names(clean):
    unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(
        blood, name, unreal.MaterialEditingLibrary.get_material_instance_static_switch_parameter_value(clean, name))
unreal.MaterialEditingLibrary.update_material_instance(blood)
assert unreal.EditorAssetLibrary.save_loaded_asset(blood, only_if_is_dirty=False)
assert unreal.EditorAssetLibrary.save_loaded_asset(blood_parent, only_if_is_dirty=False)

with unreal.ScopedEditorTransaction("Repair floor blood paint UVs and material pairing"):
    floor.modify()
    component.modify()
    paint.modify()
    assert component.set_static_mesh(mesh)
    pairs = list(paint.blood_enabled_material_pairs)
    for pair in pairs:
        if pair.clean_material == clean: pair.blood_material = blood
    paint.set_editor_property("blood_enabled_material_pairs", pairs)
assert unreal.EditorLoadingAndSavingUtils.save_packages([ed.get_editor_world().get_outermost()], True)
(out / "repair.json").write_text(json.dumps({
    "mesh": mesh.get_path_name(), "clean": clean.get_path_name(), "blood": blood.get_path_name(),
    "floor": floor.get_path_name(), "bounds": str(box),
    "blueprint_unchanged_by_repair": True,
    "map_sha256": hashlib.sha256((root / "Content/explosionVFX.umap").read_bytes()).hexdigest()
}, indent=2), encoding="utf-8")
print("FLOOR_PAINT_ASSETS_REPAIRED")
