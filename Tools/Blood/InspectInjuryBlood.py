"""Read-only blood managers, receivers and live spawned emitters."""
import json, pathlib, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out = pathlib.Path(unreal.Paths.project_saved_dir()) / "Diagnostics/InjuryBlood"
out.mkdir(parents=True, exist_ok=True)
def export(obj, name):
    t = unreal.AssetExportTask()
    t.object = obj
    t.filename = str(out / (name + ".txt"))
    t.exporter = unreal.ObjectExporterT3D()
    t.automated = True
    t.prompt = False
    t.replace_identical = True
    unreal.Exporter.run_asset_export_task(t)
def capture(world, tag):
    rows = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        grids = a.get_components_by_class(unreal.ProphecyFoliageDecalGridComponent)
        ns = a.get_components_by_class(unreal.NiagaraComponent)
        if not (grids or ns or any(s in a.get_actor_label().lower() for s in ["blood", "floor", "sword", "decal"])):
            continue
        row = {"actor": a.get_path_name(), "label": a.get_actor_label(), "class": a.get_class().get_name()}
        if grids or ns or "floor" in a.get_actor_label().lower():
            export(a, tag + "_" + a.get_name())
        if hasattr(a, "get_debug_stats_string"):
            row["paint"] = a.get_debug_stats_string()
        row["grids"] = [{"stats": g.get_foliage_decal_grid_stats_string(),
                         "material": str(g.get_editor_property("decal_material")),
                         "decals": [{"location": str(d.get_world_location()), "size": str(d.get_editor_property("decal_size")),
                                     "material": str(d.get_decal_material())}
                                    for d in g.get_active_foliage_grid_decals()]} for g in grids]
        row["ns"] = [{"asset": str(n.get_asset()), "active": n.is_active(),
                      "component": n.get_path_name()} for n in ns]
        for p in ["floor", "decal manager", "blood paint manager"]:
            try: row[p] = str(a.get_editor_property(p))
            except Exception: pass
        rows.append(row)
    return rows
result = {"play": bool(ed.get_game_world()), "editor": capture(ed.get_editor_world(), "editor")}
if ed.get_game_world():
    result["runtime"] = capture(ed.get_game_world(), "runtime")
export(unreal.load_asset("/Game/_mygame/blood2/A_DecalManager"), "manager")
(out / "state.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
