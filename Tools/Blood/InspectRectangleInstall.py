import json, pathlib, sys, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
dirty = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() + unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
grids = []
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    for c in actor.get_components_by_class(unreal.ProphecyFoliageDecalGridComponent):
        grids.append({"actor": actor.get_path_name(), "component": c.get_path_name(),
                      "settings": {p: str(c.get_editor_property(p)) for p in [
                          "cell_size_cm", "grid_origin", "max_active_decals", "max_merge_level",
                          "merge_process_interval_seconds", "merge_budget_ms", "decal_material",
                          "decal_padding", "projection_depth_cm", "projection_surface_offset_cm",
                          "max_merges_per_pass", "max_merge_checks_per_pass", "auto_process_merges"]}})
data = {"world": world.get_path_name(), "play": bool(ed.get_game_world()),
        "dirty": [p.get_path_name() for p in dirty], "grids": grids}
out = pathlib.Path(unreal.Paths.project_dir()) / "Saved/Diagnostics/BloodRectangleInstall"
out.mkdir(parents=True, exist_ok=True)
(out / ("inspection-final.json" if "--final" in sys.argv else "inspection.json")).write_text(json.dumps(data, indent=2), encoding="utf-8")
print(json.dumps(data))
