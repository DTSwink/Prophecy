"""Bake the visible UEFN FK pose to a one-pose Unreal Pose Asset."""

import json

import unreal


SEQUENCE_PATH = "/Game/_mygame/MetaHumans/NewLevelSequence"
UEFN_BINDING_NAME = "SKM_UEFN_Mannequin3"
ASSET_FOLDER = "/Game/_mygame/MetaHumans/Poses"
POSE_BASENAME = "PA_UEFN_ModifiedPose"
SOURCE_BASENAME = "AS_UEFN_ModifiedPose_Source"


def unique_name(base_name):
    candidate = base_name
    suffix = 2
    while unreal.EditorAssetLibrary.does_asset_exist(
        ASSET_FOLDER + "/" + candidate
    ):
        candidate = "{}_{}".format(base_name, suffix)
        suffix += 1
    return candidate


def find_component():
    for actor in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors():
        if actor.get_actor_label() == UEFN_BINDING_NAME:
            component = actor.get_component_by_class(
                unreal.SkeletalMeshComponent
            )
            if component is not None:
                return component
    raise RuntimeError("Could not find the bound UEFN skeletal component")


def main():
    sequence = unreal.load_asset(SEQUENCE_PATH)
    if sequence is None:
        raise RuntimeError("Missing sequence: " + SEQUENCE_PATH)

    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()

    binding = sequence.find_binding_by_name(UEFN_BINDING_NAME)
    if not binding.is_valid():
        raise RuntimeError("Invalid UEFN sequence binding")

    # Refuse to capture the double-deformed comparison state.
    body_binding = sequence.find_binding_by_name(
        "test_UEFNFit_ExportedBody5"
    )
    body_proxies = [
        proxy
        for proxy in unreal.ControlRigSequencerLibrary.get_control_rigs(sequence)
        if body_binding.is_valid() and proxy.track in body_binding.get_tracks()
    ]
    if body_proxies:
        body_section = body_proxies[0].track.get_section_to_key()
        if body_section is not None and body_section.is_active():
            raise RuntimeError(
                "Body FK section is active; refusing to capture the wrong comparison state"
            )

    component = find_component()
    skeletal_mesh = component.get_skeletal_mesh_asset()
    if skeletal_mesh is None:
        raise RuntimeError("UEFN component has no skeletal mesh")
    skeleton = skeletal_mesh.skeleton
    if skeleton is None:
        raise RuntimeError("UEFN skeletal mesh has no Skeleton asset")

    unreal.EditorAssetLibrary.make_directory(ASSET_FOLDER)
    pose_name = unique_name(POSE_BASENAME)
    source_name = unique_name(SOURCE_BASENAME)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    created_paths = []

    try:
        anim_factory = unreal.AnimSequenceFactory()
        anim_factory.target_skeleton = skeleton
        anim_factory.preview_skeletal_mesh = skeletal_mesh
        source_animation = asset_tools.create_asset(
            source_name,
            ASSET_FOLDER,
            unreal.AnimSequence,
            anim_factory,
        )
        if source_animation is None:
            raise RuntimeError("Could not create the source AnimSequence")
        created_paths.append(source_animation.get_path_name())

        export_options = unreal.AnimSeqExportOption()
        export_options.export_transforms = True
        export_options.export_morph_targets = False
        export_options.export_attribute_curves = False
        export_options.export_material_curves = False
        export_options.record_in_world_space = False
        export_options.evaluate_all_skeletal_mesh_components = False
        export_options.use_custom_time_range = True
        export_options.custom_start_frame = unreal.FrameNumber(value=0)
        export_options.custom_end_frame = unreal.FrameNumber(value=0)

        world = unreal.get_editor_subsystem(
            unreal.UnrealEditorSubsystem
        ).get_editor_world()
        if not unreal.SequencerTools.export_anim_sequence(
            world,
            sequence,
            source_animation,
            export_options,
            binding,
            False,
        ):
            raise RuntimeError("Sequencer failed to export the UEFN pose")

        frame_count = unreal.AnimationLibrary.get_num_frames(source_animation)
        key_count = unreal.AnimationLibrary.get_num_keys(source_animation)
        if frame_count != 1:
            raise RuntimeError(
                "Expected a one-frame export, got {} frames".format(frame_count)
            )

        pose_factory = unreal.PoseAssetFactory()
        pose_factory.source_animation = source_animation
        pose_asset = asset_tools.create_asset(
            pose_name,
            ASSET_FOLDER,
            unreal.PoseAsset,
            pose_factory,
        )
        if pose_asset is None:
            raise RuntimeError("Could not create the Pose Asset")
        created_paths.append(pose_asset.get_path_name())

        if pose_asset.get_skeleton() != skeleton:
            raise RuntimeError("Pose Asset was created on the wrong Skeleton")
        pose_names = [str(name) for name in pose_asset.get_pose_names()]
        if len(pose_names) not in (1, 2):
            raise RuntimeError(
                "Unexpected stored pose count: {}".format(pose_names)
            )
        pose_asset.rename_pose(
            unreal.Name(pose_names[0]),
            unreal.Name("UEFN_Modified"),
        )
        if len(pose_names) == 2:
            # UE represents a zero-duration static AnimSequence with matching
            # start/end samples. Keep the second identical sample explicitly
            # named as a hold pose instead of leaving an ambiguous Pose_1.
            pose_asset.rename_pose(
                unreal.Name(pose_names[1]),
                unreal.Name("UEFN_Modified_Hold"),
            )
        pose_names = [str(name) for name in pose_asset.get_pose_names()]

        if not unreal.EditorAssetLibrary.save_loaded_asset(
            source_animation,
            False,
        ):
            raise RuntimeError("Failed to save source AnimSequence")
        if not unreal.EditorAssetLibrary.save_loaded_asset(pose_asset, False):
            raise RuntimeError("Failed to save Pose Asset")

        report = {
            "pose_asset": pose_asset.get_path_name(),
            "source_animation": source_animation.get_path_name(),
            "skeleton": skeleton.get_path_name(),
            "pose_names": pose_names,
            "source_frames": frame_count,
            "source_keys": key_count,
            "body_fk_active": False,
            "saved": True,
        }
        print("UEFN_POSE_ASSET=" + json.dumps(report, sort_keys=True))
    except Exception:
        for path in reversed(created_paths):
            try:
                unreal.EditorAssetLibrary.delete_asset(path)
            except Exception as cleanup_error:
                unreal.log_error(
                    "Failed to clean up {}: {}".format(path, cleanup_error)
                )
        raise


main()
