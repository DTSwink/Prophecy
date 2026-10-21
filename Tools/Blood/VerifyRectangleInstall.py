"""Quick owned PIE check of the actual placed manager; never saves or edits its BP."""
import hashlib, json, pathlib, time, traceback, unreal
root = pathlib.Path(unreal.Paths.project_dir())
out = root / "Saved/Diagnostics/BloodRectangleInstall"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "Leave user Play untouched"
assert ed.get_editor_world().get_path_name() == "/Game/explosionVFX.explosionVFX"
preserved = json.loads((out / "preservation.json").read_text(encoding="utf-8"))
for path, digest in preserved["hashes"].items():
    assert hashlib.sha256((root / path).read_bytes()).hexdigest() == digest, path
blood_rect_check = {"start": time.monotonic(), "handle": None, "owned": True}

def blood_rect_tick(dt):
    try:
        world = ed.get_game_world()
        if not world:
            if time.monotonic() - blood_rect_check["start"] > 30:
                raise RuntimeError("PIE initialization timeout")
            return
        grids = []
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
            grids.extend(actor.get_components_by_class(unreal.ProphecyFoliageDecalGridComponent))
        assert len(grids) == 1, len(grids)
        grid = grids[0]
        assert "A_DecalManager" in grid.get_path_name()
        grid.set_merge_processing_enabled(False)
        cell = grid.get_editor_property("cell_size_cm")
        origin = grid.get_editor_property("grid_origin")
        before = grid.get_editor_property("total_cells_spawned")
        for y in range(2):
            for x in range(8):
                grid.add_floor_stain_to_grid(
                    unreal.Vector(origin.x + (x + .5) * cell, origin.y + (y + .5) * cell, 0),
                    unreal.Vector(0, 0, 1), 0)
        for _ in range(64):
            if grid.get_editor_property("pending_merge_count") == 0:
                break
            grid.process_pending_merges()
        decals = grid.get_active_foliage_grid_decals()
        assert grid.get_editor_property("total_cells_spawned") - before == 16
        assert len(decals) == 1, grid.get_foliage_decal_grid_stats_string()
        size = decals[0].get_editor_property("decal_size")
        padding = grid.get_editor_property("decal_padding")
        assert abs(size.y * 2 - 2 * cell * padding) < .01, str(size)
        assert abs(size.z * 2 - 8 * cell * padding) < .01, str(size)
        blood_rect_check.update(success=True, manager=grid.get_path_name(),
                                stats=grid.get_foliage_decal_grid_stats_string(),
                                projector_cm=[size.z * 2, size.y * 2, size.x * 2],
                                preserved_asset_hashes=True)
    except Exception:
        blood_rect_check.update(success=False, error=traceback.format_exc())
    unreal.unregister_slate_post_tick_callback(blood_rect_check["handle"])
    blood_rect_check["handle"] = None
    if blood_rect_check["owned"]:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    (out / "live-verification.json").write_text(json.dumps(blood_rect_check, indent=2), encoding="utf-8")

blood_rect_check["handle"] = unreal.register_slate_post_tick_callback(blood_rect_tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print("Owned brief rectangle verification started")
