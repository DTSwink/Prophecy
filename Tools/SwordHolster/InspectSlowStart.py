"""Export the live sword Blueprint and clock settings without modifying them."""
import json, pathlib, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out = pathlib.Path(unreal.Paths.project_saved_dir()) / "Diagnostics/SceneClock"
out.mkdir(parents=True, exist_ok=True)
bp = unreal.load_asset("/Game/_mygame/sword/A_Sword")
task = unreal.AssetExportTask()
task.object, task.filename = bp, str(out / "sword-current.txt")
task.exporter = unreal.ObjectExporterT3D()
task.automated, task.prompt, task.replace_identical = True, False, True
assert unreal.Exporter.run_asset_export_task(task)
world = ed.get_game_world() or ed.get_editor_world()
for command in ["getall Engine bUseFixedFrameRate", "getall Engine FixedFrameRate"]:
    unreal.SystemLibrary.execute_console_command(world, command)
result = {"play": bool(ed.get_game_world()),
          "cap": unreal.SystemLibrary.get_console_variable_float_value("t.MaxFPS"),
          "dirty": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
                    + unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
(out / "sword-before.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
