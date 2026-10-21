"""Inspect and save the new BP control after reviewing the exported graph diff."""
import json, pathlib, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
root = pathlib.Path(unreal.Paths.project_dir()).resolve()
out = root / "Saved/Diagnostics/SkeletalBloodBrush"
bp = unreal.load_asset("/Game/_mygame/blood2/A_DecalManager")
cdo = unreal.get_default_object(bp.generated_class())
rows = [{"object": cdo.get_path_name(),
         "skeletal_radius": cdo.get_editor_property("Skeletal Brush Radius"),
         "ordinary_radius": cdo.get_editor_property("brush radius")}]
for a in unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(), unreal.Actor):
    if a.get_class() == bp.generated_class():
        rows.append({"object": a.get_path_name(), "label": a.get_actor_label(),
                     "skeletal_radius": a.get_editor_property("Skeletal Brush Radius"),
                     "ordinary_radius": a.get_editor_property("brush radius")})
assert all(r["skeletal_radius"] == 3.0 for r in rows)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([bp])
dirty = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
         + unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
result = {"values": rows, "dirty": dirty, "play": False}
(out / "final.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
