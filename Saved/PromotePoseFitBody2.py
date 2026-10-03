import importlib.util
import os

import unreal

BODY = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody"
BLUEPRINT = "/Game/_mygame/MetaHumans/BP_test_UEFNDirect"
POSE_FIT_BODY = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody_PoseFitTest"

# Point any level components at the pose-fit test body so nothing references
# the old default body, then delete it.
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
pose_fit_body = unreal.load_asset(POSE_FIT_BODY)
for actor in actors:
    for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        asset = component.get_skinned_asset()
        if asset and asset.get_path_name().startswith(BODY + "."):
            component.set_skeletal_mesh_asset(pose_fit_body)
            print("RETARGETED_COMPONENT|{}|{}".format(actor.get_actor_label(), component.get_name()))

if unreal.EditorAssetLibrary.does_asset_exist(BODY):
    if not unreal.EditorAssetLibrary.delete_asset(BODY):
        raise RuntimeError("Could not delete old default body")
    print("DELETED|" + BODY)
if unreal.EditorAssetLibrary.does_asset_exist(BODY):
    raise RuntimeError("Old default body still exists after delete")

script = os.path.join(
    unreal.Paths.project_dir(), "Tools", "MetaHuman", "build_uefn_direct_metahuman.py"
)
spec = importlib.util.spec_from_file_location("build_uefn_direct_metahuman", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.main()
print("PROMOTION_BUILD_AND_AUDIT_DONE")
