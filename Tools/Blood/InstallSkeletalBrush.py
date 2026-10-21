"""Minimal live build and targeted BP addition; preserve unrelated dirty assets."""
import json, pathlib, shutil, unreal, sys
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
root = pathlib.Path(unreal.Paths.project_dir()).resolve()
out = root / "Saved/Diagnostics/SkeletalBloodBrush"
out.mkdir(parents=True, exist_ok=True)
bp = unreal.load_asset("/Game/_mygame/blood2/A_DecalManager")
def export(name):
    t = unreal.AssetExportTask()
    t.object, t.filename = bp, str(out / (name + ".txt"))
    t.exporter = unreal.ObjectExporterT3D()
    t.automated, t.prompt, t.replace_identical = True, False, True
    assert unreal.Exporter.run_asset_export_task(t)
def dirty():
    return [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
            + unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if "--build" in sys.argv:
    p = root / "Content/_mygame/blood2/A_DecalManager.uasset"
    if not (out / "A_DecalManager.before.uasset").exists():
        shutil.copy2(p, out / "A_DecalManager.before.uasset")
    export("before-build")
    (out / "dirty-before.json").write_text(json.dumps(dirty()), encoding="utf-8")
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "LiveCoding.CompileSync")
    print("SKELETAL_BRUSH_BUILD_RETURNED")
else:
    export("before-install")
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "Prophecy.Blood.WireExperiment")
    export("after-install")
    print("SKELETAL_BRUSH_INSTALLED_UNSAVED", dirty())
