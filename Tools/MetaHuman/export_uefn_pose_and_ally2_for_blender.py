"""Export the exact sources for manual UEFN-skeleton rigging in Blender.

The UEFN mesh is exported in its untouched reference state.  The previously
saved one-frame UEFN pose is exported as a separate animation-only FBX so that
Blender can pose the deform armature without changing its rest matrices.

The current ally2 MetaHuman body and face skeletal meshes are exported only as
geometry/skinning sources.  This script writes no Unreal packages or level
state.
"""

import json
import os

import unreal


PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")

SOURCES = {
    "uefn_mesh": (
        "/Game/_mygame/SKM_UEFN_Mannequin",
        "ManualRig_UEFN_Mannequin_RigMesh.fbx",
        False,
    ),
    "uefn_pose": (
        "/Game/_mygame/MetaHumans/Poses/AS_UEFN_ModifiedPose_Source",
        "ManualRig_UEFN_ModifiedPose.fbx",
        True,
    ),
    "metahuman_body": (
        "/Game/_mygame/MetaHumans/ally2/Body/SKM_test_UEFNFit_BodyMesh",
        "ManualRig_ally2_Body.fbx",
        False,
    ),
    "metahuman_face": (
        "/Game/_mygame/MetaHumans/ally2/Face/SKM_test_UEFNFit_FaceMesh",
        "ManualRig_ally2_Face.fbx",
        False,
    ),
}


def export_asset(asset, filename, is_animation):
    options = unreal.FbxExportOption()
    options.set_editor_property("ascii", False)
    options.set_editor_property("collision", False)
    options.set_editor_property("level_of_detail", False)
    options.set_editor_property("export_morph_targets", False)
    options.set_editor_property("vertex_color", False)
    options.set_editor_property("force_front_x_axis", False)
    if is_animation:
        options.set_editor_property("export_preview_mesh", False)
        options.set_editor_property("map_skeletal_motion_to_root", False)
        options.set_editor_property("export_local_time", True)

    output = os.path.join(EXCHANGE, filename)
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
    return {
        "file": output,
        "bytes": size,
        "errors": errors,
    }


def main():
    os.makedirs(EXCHANGE, exist_ok=True)
    loaded = {}
    for key, (asset_path, _filename, _is_animation) in SOURCES.items():
        asset = unreal.load_asset(asset_path)
        if asset is None:
            raise RuntimeError("Missing required asset: " + asset_path)
        loaded[key] = asset

    uefn_skeleton = loaded["uefn_mesh"].get_editor_property("skeleton")
    pose_skeleton = loaded["uefn_pose"].get_skeleton()
    if uefn_skeleton is None or pose_skeleton != uefn_skeleton:
        raise RuntimeError(
            "Saved pose is not authored on the untouched UEFN skeleton: mesh={} pose={}".format(
                uefn_skeleton.get_path_name() if uefn_skeleton else None,
                pose_skeleton.get_path_name() if pose_skeleton else None,
            )
        )

    frame_count = unreal.AnimationLibrary.get_num_frames(loaded["uefn_pose"])
    key_count = unreal.AnimationLibrary.get_num_keys(loaded["uefn_pose"])
    if frame_count != 1:
        raise RuntimeError(
            "Expected the saved UEFN pose to contain one frame, got {}".format(
                frame_count
            )
        )

    report = {
        "technique": (
            "untouched mesh FBX plus separate one-frame AnimSequence FBX; "
            "pose is applied in Blender without changing rest matrices"
        ),
        "saved_unreal_assets": False,
        "uefn_skeleton": uefn_skeleton.get_path_name(),
        "uefn_pose_frames": frame_count,
        "uefn_pose_keys": key_count,
        "sources": {},
    }
    for key, (asset_path, filename, is_animation) in SOURCES.items():
        asset = loaded[key]
        entry = {
            "asset": asset_path,
            "class": asset.get_class().get_path_name(),
            "is_animation": is_animation,
        }
        entry.update(export_asset(asset, filename, is_animation))
        report["sources"][key] = entry

    report_path = os.path.join(EXCHANGE, "ManualRig_UnrealExport_Audit.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print("MANUAL_RIG_UNREAL_EXPORT=" + json.dumps(report, sort_keys=True))


main()
