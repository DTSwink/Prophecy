"""Mirror the working transient UEFN left-leg inverse onto the right leg.

The rotations are copied through the mannequin's mirrored FK control bases.
The translations are then solved from reflected component-space joint
positions, avoiding the offset caused by copying local translations verbatim.
Nothing is saved, and the original right-leg keys are restored on failure.
"""

import json

import unreal


SEQUENCE_PATH = "/Game/_mygame/MetaHumans/NewLevelSequence"
UEFN_BINDING_NAME = "SKM_UEFN_Mannequin3"
FRAME = unreal.FrameNumber(value=0)
JOINTS = ("thigh", "calf", "foot")
MAX_CONTROL_TRANSLATION_CM = 3.0
MAX_JOINT_MIRROR_ERROR_CM = 0.02
MAX_BALL_MIRROR_ERROR_CM = 0.25


def key(kind, name):
    return unreal.RigElementKey(type=kind, name=name)


def bone(name):
    return key(unreal.RigElementType.BONE, name)


def control(name):
    return key(unreal.RigElementType.CONTROL, name + "_CONTROL")


def mirror_position(position):
    return unreal.Vector(-position.x, position.y, position.z)


def find_rig(sequence):
    binding = sequence.find_binding_by_name(UEFN_BINDING_NAME)
    if not binding.is_valid():
        raise RuntimeError("Invalid UEFN binding")
    proxies = [
        proxy
        for proxy in unreal.ControlRigSequencerLibrary.get_control_rigs(sequence)
        if proxy.track in binding.get_tracks()
    ]
    if len(proxies) != 1:
        raise RuntimeError(
            "Expected one UEFN Control Rig, found {}".format(len(proxies))
        )
    return proxies[0].control_rig


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


def set_local(sequence, rig, name, value):
    unreal.ControlRigSequencerLibrary.set_local_control_rig_transform(
        sequence,
        rig,
        name + "_CONTROL",
        FRAME,
        value,
        unreal.MovieSceneTimeUnit.DISPLAY_RATE,
        True,
    )


def refresh():
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()


def main():
    sequence = unreal.load_asset(SEQUENCE_PATH)
    if sequence is None:
        raise RuntimeError("Missing sequence: " + SEQUENCE_PATH)
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
    refresh()

    rig = find_rig(sequence)
    hierarchy = rig.get_hierarchy()
    component_world = find_component().get_world_transform()

    saved_right = {
        joint: hierarchy.get_local_transform(control(joint + "_r"), False)
        for joint in JOINTS
    }
    source_left = {
        joint: hierarchy.get_local_transform(control(joint + "_l"), False)
        for joint in JOINTS
    }
    left_globals = {
        joint: hierarchy.get_global_transform(bone(joint + "_l"), False)
        for joint in JOINTS
    }
    left_ball = hierarchy.get_global_transform(bone("ball_l"), False)

    try:
        # UEFN's left/right FK control bases are authored as mirror pairs.
        # Matching local rotation values therefore produces the mirrored
        # spatial rotation.  Translations are corrected separately below.
        for joint in JOINTS:
            set_local(sequence, rig, joint + "_r", source_left[joint])
        refresh()

        # Solve translations while locking the native mirrored local rotation.
        # A direct world setter can rewrite the local rotation on this leg, so
        # alternate the positional solve with a rotation restore.  The solve is
        # linear and converges in a few passes.
        for joint in JOINTS:
            locked_rotation = source_left[joint].rotation.rotator()
            locked_scale = source_left[joint].scale3d
            for _iteration in range(4):
                current = hierarchy.get_global_transform(
                    bone(joint + "_r"),
                    False,
                )
                target_component = unreal.Transform(
                    location=mirror_position(
                        left_globals[joint].translation
                    ),
                    rotation=current.rotation.rotator(),
                    scale=current.scale3d,
                )
                target_world = unreal.MathLibrary.compose_transforms(
                    target_component,
                    component_world,
                )
                unreal.ControlRigSequencerLibrary.set_control_rig_world_transform(
                    sequence,
                    rig,
                    joint + "_r_CONTROL",
                    FRAME,
                    target_world,
                    unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                    True,
                )
                refresh()
                solved = hierarchy.get_local_transform(
                    control(joint + "_r"),
                    False,
                )
                locked = unreal.Transform(
                    location=solved.translation,
                    rotation=locked_rotation,
                    scale=locked_scale,
                )
                set_local(sequence, rig, joint + "_r", locked)
                refresh()
        refresh()

        # Aim the foot so its ball joint lands on the reflected left ball.
        # This removes the remaining mirrored-basis twist without translating
        # the ball bone itself.
        foot_now = hierarchy.get_global_transform(bone("foot_r"), False)
        ball_now = hierarchy.get_global_transform(bone("ball_r"), False)
        foot_target = mirror_position(left_globals["foot"].translation)
        ball_target = mirror_position(left_ball.translation)
        current_axis = (ball_now.translation - foot_now.translation).normal()
        target_axis = (ball_target - foot_target).normal()
        correction = current_axis.find_quat_between_normals(target_axis)
        candidates = [
            correction * foot_now.rotation,
            foot_now.rotation * correction,
        ]
        candidate_errors = []
        for candidate in candidates:
            target_component = unreal.Transform(
                location=foot_target,
                rotation=candidate.rotator(),
                scale=foot_now.scale3d,
            )
            target_world = unreal.MathLibrary.compose_transforms(
                target_component,
                component_world,
            )
            unreal.ControlRigSequencerLibrary.set_control_rig_world_transform(
                sequence,
                rig,
                "foot_r_CONTROL",
                FRAME,
                target_world,
                unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                True,
            )
            refresh()
            trial_ball = hierarchy.get_global_transform(
                bone("ball_r"),
                False,
            )
            candidate_errors.append(
                (trial_ball.translation - ball_target).length()
            )
        best = min(range(len(candidates)), key=lambda i: candidate_errors[i])
        best_component = unreal.Transform(
            location=foot_target,
            rotation=candidates[best].rotator(),
            scale=foot_now.scale3d,
        )
        unreal.ControlRigSequencerLibrary.set_control_rig_world_transform(
            sequence,
            rig,
            "foot_r_CONTROL",
            FRAME,
            unreal.MathLibrary.compose_transforms(
                best_component,
                component_world,
            ),
            unreal.MovieSceneTimeUnit.DISPLAY_RATE,
            True,
        )
        refresh()

        joint_errors = {}
        translation_lengths = {}
        for joint in JOINTS:
            actual = hierarchy.get_global_transform(
                bone(joint + "_r"),
                False,
            )
            target = mirror_position(left_globals[joint].translation)
            joint_errors[joint + "_r"] = (
                actual.translation - target
            ).length()
            translation_lengths[joint + "_r"] = hierarchy.get_local_transform(
                control(joint + "_r"),
                False,
            ).translation.length()

        right_ball = hierarchy.get_global_transform(bone("ball_r"), False)
        ball_error = (
            right_ball.translation - mirror_position(left_ball.translation)
        ).length()

        if max(joint_errors.values()) > MAX_JOINT_MIRROR_ERROR_CM:
            raise RuntimeError(
                "Right leg joint mirror failed: {}".format(joint_errors)
            )
        if max(translation_lengths.values()) > MAX_CONTROL_TRANSLATION_CM:
            raise RuntimeError(
                "Right leg requires excessive translation: {}".format(
                    translation_lengths
                )
            )
        if ball_error > MAX_BALL_MIRROR_ERROR_CM:
            raise RuntimeError(
                "Right foot orientation did not mirror; ball error {:.4f} cm".format(
                    ball_error
                )
            )

        print(
            "RIGHT_LEG_MIRROR_FIX="
            + json.dumps(
                {
                    "joint_error_cm": joint_errors,
                    "ball_error_cm": ball_error,
                    "control_translation_cm": translation_lengths,
                    "saved": False,
                },
                sort_keys=True,
            )
        )
    except Exception:
        for joint in JOINTS:
            set_local(sequence, rig, joint + "_r", saved_right[joint])
        refresh()
        raise


main()
