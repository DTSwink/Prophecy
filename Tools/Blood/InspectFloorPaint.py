"""Read-only floor paint eligibility and routing snapshot."""
import json, pathlib, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out = pathlib.Path(unreal.Paths.project_saved_dir()) / "Diagnostics/InjuryBlood"
rows = []
for w in [ed.get_editor_world(), ed.get_game_world()]:
    if not w:
        continue
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        if isinstance(a, unreal.ProphecyBloodTexturePaintManager):
            rows.append({"actor": a.get_path_name(), "pairs": [
                {"clean": str(p.clean_material), "blood": str(p.blood_material)}
                for p in a.blood_enabled_material_pairs],
                "auto_create": a.editor_auto_create_blood_materials,
                "stats": a.get_debug_stats_string()})
        if a.get_class().get_name().startswith("A_DecalManager_C"):
            rows.append({"manager": a.get_path_name(), "floor": str(a.get_editor_property("floor")),
                         "paint": str(a.get_editor_property("paint manager"))})
bp = unreal.load_asset("/Game/_mygame/blood2/A_DecalManager")
t = unreal.AssetExportTask()
t.object, t.filename = bp, str(out / "manager-current.txt")
t.exporter = unreal.ObjectExporterT3D()
t.automated, t.prompt, t.replace_identical = True, False, True
unreal.Exporter.run_asset_export_task(t)
report = {"play": bool(ed.get_game_world()), "rows": rows,
          "dirty": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
                    + unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
(out / "floor-paint-inspection.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
