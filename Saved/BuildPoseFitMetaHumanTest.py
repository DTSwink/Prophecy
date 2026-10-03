import json
import os

import unreal

SOURCE_BODY = "/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh"
UEFN_MESH = "/Game/_mygame/SKM_UEFN_Mannequin"
SOURCE_BLUEPRINT = "/Game/MetaHumans/test_UEFNExactFull/BP_test_UEFNExactFull"
FACE_ANIM = "/Game/MetaHumans/Common/Face/Face_AnimBP"
BODY_OUTPUT = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody_PoseFitTest"
BLUEPRINT_OUTPUT = "/Game/_mygame/MetaHumans/BP_test_UEFNDirect_PoseFitTest"

for path in (BLUEPRINT_OUTPUT, BODY_OUTPUT):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        if not unreal.EditorAssetLibrary.delete_asset(path):
            raise RuntimeError("Could not delete existing test asset: " + path)

unreal.SystemLibrary.execute_console_command(
    None,
    "Prophecy.MetaHuman.BuildUEFNBody {} {} {}".format(
        SOURCE_BODY, UEFN_MESH, BODY_OUTPUT
    ),
)
body = unreal.load_asset(BODY_OUTPUT)
if not isinstance(body, unreal.SkeletalMesh):
    raise RuntimeError("Could not build/load pose-fit test body")

weights_path = os.path.join(
    unreal.Paths.project_saved_dir(), "PoseFit", "reduced_weights.json"
)
with open(weights_path, "r", encoding="utf-8") as handle:
    reduced = json.load(handle)["weights"]

modifier = unreal.SkinWeightModifier()
if not modifier.set_skeletal_mesh(body):
    raise RuntimeError("Could not open pose-fit test body for weight editing")
if modifier.get_num_vertices() != len(reduced):
    raise RuntimeError(
        "Vertex count mismatch: mesh={} fit={}".format(
            modifier.get_num_vertices(), len(reduced)
        )
    )

for vertex_id, vertex_weights in enumerate(reduced):
    if not modifier.set_vertex_weights(vertex_id, vertex_weights, True):
        raise RuntimeError("Could not set weights on vertex {}".format(vertex_id))
if not modifier.commit_weights_to_skeletal_mesh():
    raise RuntimeError("Could not commit pose-fit weights")

mesh_editor = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
if not mesh_editor.remove_lods(body, [1, 2]):
    raise RuntimeError("Could not remove lower test LODs")
if not mesh_editor.regenerate_lod(body, 3, True, False):
    raise RuntimeError("Could not regenerate test LODs")
unreal.EditorAssetLibrary.save_loaded_asset(body, only_if_is_dirty=False)

unreal.SystemLibrary.execute_console_command(
    None,
    "Prophecy.MetaHuman.BuildUEFNBlueprint {} {} {} {}".format(
        SOURCE_BLUEPRINT, BODY_OUTPUT, FACE_ANIM, BLUEPRINT_OUTPUT
    ),
)
blueprint = unreal.load_asset(BLUEPRINT_OUTPUT)
if not isinstance(blueprint, unreal.Blueprint):
    raise RuntimeError("Could not build pose-fit test Blueprint")
unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=False)

print(
    "POSEFIT_TEST_BUILT|body={}|blueprint={}|vertices={}".format(
        body.get_path_name(), blueprint.get_path_name(), len(reduced)
    )
)
