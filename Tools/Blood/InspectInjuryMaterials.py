import json, pathlib, unreal
out = pathlib.Path(unreal.Paths.project_saved_dir()) / "Diagnostics/InjuryBlood"
report = {}
for name, path in [("blood", "/Game/_mygame/blood2/MI_blooddecal"),
                   ("floor", "/Engine/OpenWorldTemplate/LandscapeMaterial/MI_ProcGrid")]:
    m = unreal.load_asset(path)
    entry = {"material": m.get_path_name(), "parent": m.parent.get_path_name()}
    for kind in ["texture", "scalar", "vector"]:
        names = getattr(unreal.MaterialEditingLibrary, "get_" + kind + "_parameter_names")(m)
        getter = getattr(unreal.MaterialEditingLibrary, "get_material_instance_" + kind + "_parameter_value")
        entry[kind] = {str(n): str(getter(m, n)) for n in names}
    report[name] = entry
    for suffix, obj in [("", m), ("_parent", m.parent)]:
        t = unreal.AssetExportTask()
        t.object = obj
        t.filename = str(out / (name + suffix + ".txt"))
        t.exporter = unreal.ObjectExporterT3D()
        t.automated = True
        t.prompt = False
        t.replace_identical = True
        unreal.Exporter.run_asset_export_task(t)
(out / "materials.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
