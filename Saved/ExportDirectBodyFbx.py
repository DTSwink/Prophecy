import json
import os

import unreal

EXPORT_DIR = os.path.join(unreal.Paths.project_dir(), "Saved", "BlenderExchange")
os.makedirs(EXPORT_DIR, exist_ok=True)

BODY = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody"

body = unreal.load_asset(BODY)
if body is None:
    raise RuntimeError("Missing " + BODY)

# 1) FBX export (geometry donor: UEFN skeleton, consistent bind pose).
options = unreal.FbxExportOption()
options.set_editor_property("ascii", False)
options.set_editor_property("collision", False)
options.set_editor_property("level_of_detail", False)
options.set_editor_property("export_morph_targets", False)
options.set_editor_property("vertex_color", False)

task = unreal.AssetExportTask()
task.set_editor_property("object", body)
task.set_editor_property("filename", os.path.join(EXPORT_DIR, "DirectBody_UEFN.fbx"))
task.set_editor_property("automated", True)
task.set_editor_property("replace_identical", True)
task.set_editor_property("prompt", False)
task.set_editor_property("options", options)
if not unreal.Exporter.run_asset_export_task(task):
    raise RuntimeError("FBX export failed: {}".format(list(task.get_editor_property("errors"))))
print("EXPORT_FBX_OK|{}".format(os.path.getsize(os.path.join(EXPORT_DIR, "DirectBody_UEFN.fbx"))))

# 2) LOD0 render vertex positions, for index mapping against source_mesh.json.
modifier = unreal.SkinWeightModifier()
if not modifier.set_skeletal_mesh(body):
    raise RuntimeError("SkinWeightModifier could not open the body")
num = modifier.get_num_vertices()
positions = []
for index in range(num):
    p = modifier.get_vertex_position(index)
    positions.append([p.x, p.y, p.z])
modifier.cancel_weights_changes()
with open(os.path.join(EXPORT_DIR, "DirectBody_positions.json"), "w", encoding="utf-8") as handle:
    json.dump({"num_vertices": num, "positions": positions}, handle)
print("EXPORT_POSITIONS_OK|{}".format(num))
print("DIRECTBODY_EXPORT_DONE")
