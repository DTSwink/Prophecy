"""Restore the transient fitted MetaHuman body and export its saved FK pose.

Run through the live Prophecy editor bridge.  The imported body asset and its
assignment to the level actor deliberately remain transient: this script never
saves a Content package or the level.
"""

import json
import os
import time

import unreal


PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
BODY_FBX = os.path.join(EXCHANGE, "Body_MH342.fbx")
POSE_FBX = os.path.join(EXCHANGE, "MetaHuman_SequencerModifiedPose.fbx")
BAKED_POSE_FBX = os.path.join(
    EXCHANGE,
    "MetaHuman_SequencerModifiedPose_BakedAnim.fbx",
)
SEQUENCE_PATH = "/Game/_mygame/MetaHumans/NewLevelSequence"
TRANSIENT_BODY_PATH = "/Game/_mygame/MetaHumans/test_UEFNFit_ExportedBody5"
BODY_ACTOR_LABEL = "test_UEFNFit_ExportedBody5"


def import_transient_body():
    body = unreal.load_asset(TRANSIENT_BODY_PATH)
    if body is not None:
        return body, False

    if not os.path.isfile(BODY_FBX):
        raise RuntimeError("Missing fitted body FBX: " + BODY_FBX)

    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", True)
    options.set_editor_property("import_animations", False)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    options.set_editor_property("create_physics_asset", False)
    options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    mesh_data = options.get_editor_property("skeletal_mesh_import_data")
    mesh_data.set_editor_property("import_morph_targets", False)
    mesh_data.set_editor_property("update_skeleton_reference_pose", False)
    mesh_data.set_editor_property("use_t0_as_ref_pose", False)
    mesh_data.set_editor_property(
        "normal_import_method",
        unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
    )

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", BODY_FBX)
    task.set_editor_property("destination_path", "/Game/_mygame/MetaHumans")
    task.set_editor_property("destination_name", "test_UEFNFit_ExportedBody5")
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("options", options)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    body = unreal.load_asset(TRANSIENT_BODY_PATH)
    if body is None:
        raise RuntimeError(
            "Transient body import failed: "
            + str(list(task.get_editor_property("imported_object_paths")))
        )
    return body, True


def find_actor(label):
    actors = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    matches = [actor for actor in actors if actor.get_actor_label() == label]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected one actor labelled {!r}, found {}".format(label, len(matches))
        )
    return matches[0]


def bake_and_export_animation(world, sequence, body):
    binding = sequence.find_binding_by_name(BODY_ACTOR_LABEL)
    if not binding.is_valid():
        raise RuntimeError("Sequence body binding is invalid: " + BODY_ACTOR_LABEL)

    factory = unreal.AnimSequenceFactory()
    factory.set_editor_property("target_skeleton", body.get_editor_property("skeleton"))
    name = "Temp_MetaHumanSequencerPose_{}".format(int(time.time()))
    animation = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name=name,
        package_path="/Game/_mygame/MetaHumans",
        asset_class=unreal.AnimSequence,
        factory=factory,
    )
    if animation is None:
        raise RuntimeError("Could not create transient AnimSequence")

    options = unreal.AnimSeqExportOption()
    options.set_editor_property("export_transforms", True)
    options.set_editor_property("export_attribute_curves", False)
    options.set_editor_property("export_material_curves", False)
    options.set_editor_property("export_morph_targets", False)
    options.set_editor_property("record_in_world_space", False)
    options.set_editor_property("evaluate_all_skeletal_mesh_components", True)
    zero_frame = unreal.FrameNumber(value=0)
    options.set_editor_property("warm_up_frames", zero_frame)
    options.set_editor_property("delay_before_start", zero_frame)
    baked = unreal.SequencerTools.export_anim_sequence(
        world,
        sequence,
        animation,
        options,
        binding,
        False,
    )
    if not baked:
        raise RuntimeError("SequencerTools.export_anim_sequence returned false")

    export_options = unreal.FbxExportOption()
    export_options.set_editor_property("ascii", False)
    export_options.set_editor_property("collision", False)
    export_options.set_editor_property("level_of_detail", False)
    export_options.set_editor_property("export_morph_targets", False)
    export_options.set_editor_property("export_preview_mesh", False)
    export_options.set_editor_property("map_skeletal_motion_to_root", False)
    export_options.set_editor_property("export_local_time", True)
    export_options.set_editor_property("force_front_x_axis", False)

    task = unreal.AssetExportTask()
    task.set_editor_property("object", animation)
    task.set_editor_property("filename", BAKED_POSE_FBX)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_identical", True)
    task.set_editor_property("prompt", False)
    task.set_editor_property("options", export_options)
    exported = unreal.Exporter.run_asset_export_task(task)
    errors = list(task.get_editor_property("errors"))
    if (
        not exported
        or not os.path.isfile(BAKED_POSE_FBX)
        or os.path.getsize(BAKED_POSE_FBX) <= 0
    ):
        raise RuntimeError("Baked animation FBX export failed: " + str(errors))

    return animation, errors


def main():
    os.makedirs(EXCHANGE, exist_ok=True)
    body, imported = import_transient_body()
    actor = find_actor(BODY_ACTOR_LABEL)
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    if component is None:
        raise RuntimeError("Body actor has no SkeletalMeshComponent")
    component.set_editor_property("skeletal_mesh", body)

    sequence = unreal.load_asset(SEQUENCE_PATH)
    if sequence is None:
        raise RuntimeError("Missing sequence: " + SEQUENCE_PATH)
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()

    rigs = unreal.ControlRigSequencerLibrary.get_control_rigs(sequence)
    if len(rigs) != 1:
        raise RuntimeError("Expected one FK Control Rig, found {}".format(len(rigs)))
    proxy = rigs[0]
    rig = proxy.control_rig
    hierarchy = rig.get_hierarchy()
    controls = hierarchy.get_controls(True)
    bones = hierarchy.get_bones(True)
    if len(controls) < 300 or len(bones) < 300:
        raise RuntimeError(
            "FK rig did not initialize from the restored body: controls={} bones={}".format(
                len(controls), len(bones)
            )
        )

    section = proxy.track.get_section_to_key()
    if section is None:
        raise RuntimeError("FK track has no section to export")

    settings = unreal.MovieSceneUserExportFBXControlRigSettings()
    settings.set_editor_property("ascii", False)
    settings.set_editor_property("export_file_name", POSE_FBX)
    exported = unreal.ControlRigSequencerLibrary.export_fbx_from_control_rig_section(
        sequence,
        section,
        settings,
    )
    if not exported or not os.path.isfile(POSE_FBX) or os.path.getsize(POSE_FBX) <= 0:
        raise RuntimeError("Control Rig FBX export failed: " + POSE_FBX)

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    baked_animation, baked_export_errors = bake_and_export_animation(
        world,
        sequence,
        body,
    )

    # Give the Blender audit a compact authoritative pose sample as well.
    sample = {}
    for name in (
        "root",
        "pelvis",
        "clavicle_l",
        "upperarm_l",
        "lowerarm_l",
        "hand_l",
        "clavicle_r",
        "upperarm_r",
        "lowerarm_r",
        "hand_r",
        "thigh_l",
        "calf_l",
        "foot_l",
        "thigh_r",
        "calf_r",
        "foot_r",
        "neck_01",
        "neck_02",
        "head",
    ):
        key = unreal.RigElementKey(
            type=unreal.RigElementType.BONE,
            name=name,
        )
        transform = hierarchy.get_global_transform(key, False)
        translation = transform.translation
        rotation = transform.rotation
        scale = transform.scale3d
        sample[name] = {
            "translation_cm": [translation.x, translation.y, translation.z],
            "rotation_xyzw": [rotation.x, rotation.y, rotation.z, rotation.w],
            "scale": [scale.x, scale.y, scale.z],
        }

    report = {
        "sequence": sequence.get_path_name(),
        "frame": 0,
        "actor": actor.get_path_name(),
        "body": body.get_path_name(),
        "body_was_imported_transiently": imported,
        "control_count": len(controls),
        "bone_count": len(bones),
        "pose_fbx": POSE_FBX,
        "pose_fbx_bytes": os.path.getsize(POSE_FBX),
        "baked_animation": baked_animation.get_path_name(),
        "baked_animation_saved": False,
        "baked_pose_fbx": BAKED_POSE_FBX,
        "baked_pose_fbx_bytes": os.path.getsize(BAKED_POSE_FBX),
        "baked_pose_export_errors": [str(error) for error in baked_export_errors],
        "sample_global_pose": sample,
        "saved_content_assets": False,
    }
    report_path = os.path.join(EXCHANGE, "MetaHuman_SequencerModifiedPose_UnrealAudit.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print("METAHUMAN_SEQUENCER_POSE=" + json.dumps(report, sort_keys=True))


main()
