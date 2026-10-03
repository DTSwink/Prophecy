import os
import unreal


subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
library = unreal.SubobjectDataBlueprintFunctionLibrary
for label, path in [
    ("pose", "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent"),
    ("cmc", "/Game/_mygame/SandboxCharacter_CMC"),
]:
    blueprint = unreal.EditorAssetLibrary.load_asset(path)
    component = None
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(blueprint):
        data = subsystem.k2_find_subobject_data_from_handle(handle)
        obj = library.get_object(data) or library.get_associated_object(data)
        if obj and obj.get_name().startswith("PhysicalMesh"):
            component = obj
            break
    if not component:
        raise RuntimeError("Missing PhysicalMesh for " + path)
    output = os.path.join(unreal.Paths.project_saved_dir(), "{}_PhysicalMesh.t3d".format(label))
    task = unreal.AssetExportTask()
    task.object = component
    task.filename = output
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    task.exporter = unreal.ObjectExporterT3D()
    success = unreal.Exporter.run_asset_export_task(task)
    print("{} success={} output={} component={}".format(label, success, output, component))
