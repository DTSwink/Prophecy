"""Correct the transient UEFN left-arm mirror in the open Sequencer.

The left/right FK control bases are not interchangeable.  Copying the right
control translations verbatim therefore preserves the rotations but offsets
the left shoulder, elbow, and wrist.  This script keeps the current left-arm
rotations and derives only the translations from the reflected component-space
positions of the already-correct right arm.

Nothing is saved.  The three existing left control values are restored if the
result is not an exact positional mirror or would require a large translation.
"""

import json
import math

import unreal


SEQUENCE_PATH = "/Game/_mygame/MetaHumans/NewLevelSequence"
UEFN_BINDING_NAME = "SKM_UEFN_Mannequin3"
FRAME = unreal.FrameNumber(value=0)
JOINTS = ("upperarm", "lowerarm", "hand")
MAX_CONTROL_TRANSLATION_CM = 3.0
MAX_MIRROR_ERROR_CM = 0.02


def bone_key(name):
    return unreal.RigElementKey(type=unreal.RigElementType.BONE, name=name)


def control_key(name):
    return unreal.RigElementKey(
        type=unreal.RigElementType.CONTROL,
        name=name + "_CONTROL",
    )


def mirrored_position(position):
    # The mannequin is Y-forward, so the sagittal mirror plane is component X=0.
    return unreal.Vector(-position.x, position.y, position.z)


def distance(a, b):
    return (a - b).length()


def find_uefn_proxy(sequence, binding):
    matches = [
        proxy
        for proxy in unreal.ControlRigSequencerLibrary.get_control_rigs(sequence)
        if proxy.track in binding.get_tracks()
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one UEFN Control Rig proxy, found {}".format(
                len(matches)
            )
        )
    return matches[0]


def find_component():
    actors = {
        actor.get_actor_label(): actor
        for actor in unreal.get_editor_subsystem(
            unreal.EditorActorSubsystem
        ).get_all_level_actors()
    }
    actor = actors.get(UEFN_BINDING_NAME)
    if actor is None:
        raise RuntimeError("Missing UEFN actor: " + UEFN_BINDING_NAME)
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    if component is None:
        raise RuntimeError("UEFN actor has no SkeletalMeshComponent")
    return component


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

    proxy = find_uefn_proxy(sequence, binding)
    rig = proxy.control_rig
    hierarchy = rig.get_hierarchy()
    component_world = find_component().get_world_transform()

    saved_left_local = {}
    left_global_before = {}
    right_global = {}
    for joint in JOINTS:
        left_name = joint + "_l"
        right_name = joint + "_r"
        saved_left_local[left_name] = hierarchy.get_local_transform(
            control_key(left_name),
            False,
        )
        left_global_before[left_name] = hierarchy.get_global_transform(
            bone_key(left_name),
            False,
        )
        right_global[right_name] = hierarchy.get_global_transform(
            bone_key(right_name),
            False,
        )

    try:
        # Parent-to-child order is required: each world-space setter derives a
        # local FK value against the already-corrected parent.
        for joint in JOINTS:
            left_name = joint + "_l"
            right_name = joint + "_r"
            old_left = left_global_before[left_name]
            target_component = unreal.Transform(
                location=mirrored_position(
                    right_global[right_name].translation
                ),
                rotation=old_left.rotation.rotator(),
                scale=old_left.scale3d,
            )
            target_world = unreal.MathLibrary.compose_transforms(
                target_component,
                component_world,
            )
            unreal.ControlRigSequencerLibrary.set_control_rig_world_transform(
                sequence,
                rig,
                left_name + "_CONTROL",
                FRAME,
                target_world,
                unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                True,
            )

        unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
        unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()

        mirror_errors = {}
        control_translation_cm = {}
        rotation_changes_deg = {}
        for joint in JOINTS:
            left_name = joint + "_l"
            right_name = joint + "_r"
            actual = hierarchy.get_global_transform(bone_key(left_name), False)
            target_position = mirrored_position(
                right_global[right_name].translation
            )
            mirror_errors[left_name] = distance(
                actual.translation,
                target_position,
            )

            local_control = hierarchy.get_local_transform(
                control_key(left_name),
                False,
            )
            control_translation_cm[left_name] = local_control.translation.length()

            relative = unreal.MathLibrary.compose_transforms(
                unreal.MathLibrary.invert_transform(
                    left_global_before[left_name]
                ),
                actual,
            ).rotation
            w = max(-1.0, min(1.0, abs(relative.w)))
            rotation_changes_deg[left_name] = math.degrees(
                2.0 * math.acos(w)
            )

        worst_error = max(mirror_errors.values())
        worst_translation = max(control_translation_cm.values())
        if worst_error > MAX_MIRROR_ERROR_CM:
            raise RuntimeError(
                "Left arm mirror verification failed: {:.4f} cm".format(
                    worst_error
                )
            )
        if worst_translation > MAX_CONTROL_TRANSLATION_CM:
            raise RuntimeError(
                "Left arm would require a large FK translation: {:.4f} cm".format(
                    worst_translation
                )
            )

        print(
            "LEFT_ARM_TRANSLATION_FIX="
            + json.dumps(
                {
                    "mirror_error_cm": mirror_errors,
                    "control_translation_cm": control_translation_cm,
                    "rotation_change_deg": rotation_changes_deg,
                    "saved": False,
                },
                sort_keys=True,
            )
        )
    except Exception:
        for joint in JOINTS:
            left_name = joint + "_l"
            unreal.ControlRigSequencerLibrary.set_local_control_rig_transform(
                sequence,
                rig,
                left_name + "_CONTROL",
                FRAME,
                saved_left_local[left_name],
                unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                True,
            )
        unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
        unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
        raise


main()
