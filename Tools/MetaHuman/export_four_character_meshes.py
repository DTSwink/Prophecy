"""Export Body and Face skeletal-mesh assets for four placed characters.

Runs inside the live Unreal editor. It exports source assets only and does not
save or modify any Unreal package, blueprint, actor, or level.
"""

import json
import os
import unreal


PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
OUTPUT_DIR = os.path.join(PROJECT, "Saved", "BlenderExchange", "FourCharacters")

CHARACTERS = {
    "BP_boss": {
        "body": "/Game/_mygame/MetaHumans/boss/Body/SKM_test_UEFNFit2_BodyMesh",
        "face": "/Game/_mygame/MetaHumans/boss/Face/SKM_test_UEFNFit2_FaceMesh",
    },
    "BP_Enemy": {
        "body": "/Game/MetaHumans/test_UEFNFit/Body/SKM_test_UEFNFit1_BodyMesh",
        "face": "/Game/MetaHumans/test_UEFNFit/Face/SKM_test_UEFNFit1_FaceMesh",
    },
    "BP_girl": {
        "body": "/Game/_mygame/MetaHumans/girl/Body/SKM_test_UEFNFit5_BodyMesh",
        "face": "/Game/_mygame/MetaHumans/girl/Face/SKM_test_UEFNFit5_FaceMesh",
    },
    "BP_savagee": {
        "body": "/Game/_mygame/MetaHumans/savagee/Body/SKM_test_UEFNFit3_BodyMesh",
        "face": "/Game/_mygame/MetaHumans/savagee/Face/SKM_test_UEFNFit3_FaceMesh",
    },
}


def export_skeletal_mesh(asset, output):
    options = unreal.FbxExportOption()
    options.set_editor_property("ascii", False)
    options.set_editor_property("collision", False)
    options.set_editor_property("level_of_detail", False)
    options.set_editor_property("export_morph_targets", False)
    options.set_editor_property("vertex_color", False)
    options.set_editor_property("force_front_x_axis", False)

    task = unreal.AssetExportTask()
    task.set_editor_property("object", asset)
    task.set_editor_property("filename", output)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_identical", True)
    task.set_editor_property("prompt", False)
    task.set_editor_property("options", options)
    succeeded = unreal.Exporter.run_asset_export_task(task)
    errors = [str(error) for error in task.get_editor_property("errors")]
    size = os.path.getsize(output) if os.path.isfile(output) else -1
    if not succeeded or size <= 0:
        raise RuntimeError(
            "FBX export failed for {}: succeeded={} bytes={} errors={}".format(
                asset.get_path_name(), succeeded, size, errors
            )
        )
    return {"file": output, "bytes": size, "errors": errors}


os.makedirs(OUTPUT_DIR, exist_ok=True)
report = {
    "output_directory": OUTPUT_DIR,
    "saved_unreal_assets": False,
    "characters": {},
}
for character, sources in CHARACTERS.items():
    entry = {}
    for part, asset_path in sources.items():
        asset = unreal.load_asset(asset_path)
        if asset is None or not isinstance(asset, unreal.SkeletalMesh):
            raise RuntimeError("Missing SkeletalMesh: " + asset_path)
        output = os.path.join(OUTPUT_DIR, "{}_{}.fbx".format(character, part.capitalize()))
        item = {
            "asset": asset.get_path_name(),
            "class": asset.get_class().get_path_name(),
        }
        item.update(export_skeletal_mesh(asset, output))
        entry[part] = item
    report["characters"][character] = entry

report_path = os.path.join(OUTPUT_DIR, "UnrealExport_Audit.json")
with open(report_path, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
print("FOUR_CHARACTER_EXPORT=" + json.dumps(report, sort_keys=True))
