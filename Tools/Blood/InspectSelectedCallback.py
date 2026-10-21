"""Read selected/placed Niagara instances and callback assignment."""
import pathlib, unreal
e = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
selected = list(e.get_selected_level_actors())
print("SELECTED", [(a.get_actor_label(), a.get_class().get_name()) for a in selected])
out = pathlib.Path(unreal.Paths.project_saved_dir()) / "Diagnostics/InjuryBlood"
for a in e.get_all_level_actors():
    if "decalmanager" in a.get_class().get_name().lower():
        print("MANAGER", a.get_actor_label(), a.get_path_name())
    for c in a.get_components_by_class(unreal.NiagaraComponent):
        print("NIAGARA", a.get_actor_label(), c.get_asset())
        t = unreal.AssetExportTask()
        t.object, t.filename = c, str(out / "selected-callback.txt")
        t.exporter = unreal.ObjectExporterT3D()
        t.automated, t.prompt, t.replace_identical = True, False, True
        unreal.Exporter.run_asset_export_task(t)
        for line in (out / "selected-callback.txt").read_text(encoding="utf-8-sig").splitlines():
            if "OverrideParameters=" in line or "InstanceParameterOverrides=" in line:
                print(line)
