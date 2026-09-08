"""Invert the saved MetaHuman FK deformation onto the UEFN mannequin.

This runs in the live editor and intentionally does not save anything.  It
creates a transient FK Control Rig track on the existing UEFN binding, keys a
single frame, verifies the resulting bone transforms, and removes the new track
again if any part of the solve fails.
"""

import json
import math
import os

import unreal


SEQUENCE_PATH = "/Game/_mygame/MetaHumans/NewLevelSequence"
BODY_BINDING_NAME = "test_UEFNFit_ExportedBody5"
UEFN_BINDING_NAME = "SKM_UEFN_Mannequin3"
FRAME = unreal.FrameNumber(value=0)


def transform_json(transform):
    translation = transform.translation
    rotation = transform.rotation
    scale = transform.scale3d
    return {
        "translation": [translation.x, translation.y, translation.z],
        "rotation_xyzw": [rotation.x, rotation.y, rotation.z, rotation.w],
        "scale": [scale.x, scale.y, scale.z],
    }


def transform_error(actual, expected):
    a = actual.translation
    e = expected.translation
    translation = math.sqrt(
        (a.x - e.x) ** 2 + (a.y - e.y) ** 2 + (a.z - e.z) ** 2
    )
    relative = unreal.MathLibrary.compose_transforms(
        unreal.MathLibrary.invert_transform(expected),
        actual,
    )
    rotation = relative.rotation
    w = max(-1.0, min(1.0, abs(rotation.w)))
    rotation_deg = math.degrees(2.0 * math.acos(w))
    return translation, rotation_deg


def find_proxy_for_track(sequence, track):
    for proxy in unreal.ControlRigSequencerLibrary.get_control_rigs(sequence):
        if proxy.track == track:
            return proxy
    return None


def main():
    sequence = unreal.load_asset(SEQUENCE_PATH)
    if sequence is None:
        raise RuntimeError("Missing sequence: " + SEQUENCE_PATH)
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    if world is None:
        raise RuntimeError("No editor world")

    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()

    body_binding = sequence.find_binding_by_name(BODY_BINDING_NAME)
    uefn_binding = sequence.find_binding_by_name(UEFN_BINDING_NAME)
    if not body_binding.is_valid() or not uefn_binding.is_valid():
        raise RuntimeError("Required sequence binding is invalid")

    existing_proxies = unreal.ControlRigSequencerLibrary.get_control_rigs(sequence)
    body_proxies = [
        proxy
        for proxy in existing_proxies
        if proxy.track in body_binding.get_tracks()
    ]
    uefn_proxies = [
        proxy
        for proxy in existing_proxies
        if proxy.track in uefn_binding.get_tracks()
    ]
    if len(body_proxies) != 1:
        raise RuntimeError(
            "Expected one Body FK rig, found {}".format(len(body_proxies))
        )
    if len(uefn_proxies) > 1:
        raise RuntimeError(
            "UEFN binding has multiple Control Rig tracks; refusing to continue"
        )

    body_rig = body_proxies[0].control_rig
    body_section = body_proxies[0].track.get_section_to_key()
    if body_rig.get_class().get_name() != "FKControlRig":
        raise RuntimeError("Body track is not FKControlRig")
    if not body_section.is_active():
        raise RuntimeError(
            "Body FK section is inactive, so its evaluated deformation is unavailable"
        )

    body_hierarchy = body_rig.get_hierarchy()
    body_bones = {str(key.name): key for key in body_hierarchy.get_bones(True)}
    if len(body_bones) != 342:
        raise RuntimeError(
            "Expected 342 Body FK bones, found {}".format(len(body_bones))
        )

    new_track = uefn_proxies[0].track if uefn_proxies else None
    created_track = False
    try:
        if new_track is None:
            new_track = unreal.ControlRigSequencerLibrary.find_or_create_control_rig_track(
                world,
                sequence,
                unreal.FKControlRig.static_class(),
                uefn_binding,
                False,
            )
            created_track = new_track is not None
        if new_track is None:
            raise RuntimeError("Could not create UEFN FK Control Rig track")
        uefn_proxy = find_proxy_for_track(sequence, new_track)
        if uefn_proxy is None:
            raise RuntimeError("Created UEFN FK track has no rig proxy")

        uefn_rig = uefn_proxy.control_rig
        uefn_hierarchy = uefn_rig.get_hierarchy()
        uefn_bone_keys = list(uefn_hierarchy.get_bones(True))
        uefn_controls = {
            str(key.name): key for key in uefn_hierarchy.get_controls(True)
        }
        shared = [
            key for key in uefn_bone_keys if str(key.name) in body_bones
        ]
        if len(shared) < 75:
            raise RuntimeError(
                "Too few shared Body/UEFN bones: {}".format(len(shared))
            )

        expected_targets = {}
        inverse_deltas = {}
        movement = {}
        for uefn_bone_key in shared:
            name = str(uefn_bone_key.name)
            control_name = name + "_CONTROL"
            if control_name not in uefn_controls:
                raise RuntimeError(
                    "UEFN FK rig is missing control " + control_name
                )

            body_key = body_bones[name]
            body_initial = body_hierarchy.get_global_transform(body_key, True)
            body_posed = body_hierarchy.get_global_transform(body_key, False)

            # Component-space delta D such that Initial * D = Posed.  Apply
            # D^-1 after the UEFN initial transform; no MetaHuman bone position
            # is used as a target.
            delta = unreal.MathLibrary.compose_transforms(
                unreal.MathLibrary.invert_transform(body_initial),
                body_posed,
            )
            inverse_delta = unreal.MathLibrary.invert_transform(delta)
            inverse_deltas[name] = inverse_delta

            uefn_initial = uefn_hierarchy.get_global_transform(
                uefn_bone_key,
                True,
            )
            target = unreal.MathLibrary.compose_transforms(
                uefn_initial,
                inverse_delta,
            )
            expected_targets[name] = target
            movement[name] = (
                target.translation - uefn_initial.translation
            ).length()

        actors = {
            actor.get_actor_label(): actor
            for actor in unreal.get_editor_subsystem(
                unreal.EditorActorSubsystem
            ).get_all_level_actors()
        }
        uefn_actor = actors.get(UEFN_BINDING_NAME)
        if uefn_actor is None:
            raise RuntimeError("Could not find bound UEFN actor in the level")
        component = uefn_actor.get_component_by_class(
            unreal.SkeletalMeshComponent
        )
        if component is None:
            raise RuntimeError("Bound UEFN actor has no SkeletalMeshComponent")
        component_world = component.get_world_transform()

        # get_bones(True) is depth-first, so parent controls are keyed before
        # children. World setters then derive stable local FK values.
        keyed_controls = []
        for uefn_bone_key in shared:
            name = str(uefn_bone_key.name)
            control_name = name + "_CONTROL"
            control_key = uefn_controls[control_name]
            control_initial = uefn_hierarchy.get_global_transform(
                control_key,
                True,
            )
            target_control_component = unreal.MathLibrary.compose_transforms(
                control_initial,
                inverse_deltas[name],
            )
            target_control_world = unreal.MathLibrary.compose_transforms(
                target_control_component,
                component_world,
            )
            unreal.ControlRigSequencerLibrary.set_control_rig_world_transform(
                sequence,
                uefn_rig,
                control_name,
                FRAME,
                target_control_world,
                unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                True,
            )
            keyed_controls.append(control_name)

        new_section = new_track.get_section_to_key()
        if new_section is None:
            raise RuntimeError("UEFN FK track has no section after keying")
        unreal.ControlRigSequencerLibrary.set_controls_mask(
            new_section,
            list(uefn_controls),
            False,
        )
        unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
        unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()

        errors = []
        for uefn_bone_key in shared:
            name = str(uefn_bone_key.name)
            actual = uefn_hierarchy.get_global_transform(uefn_bone_key, False)
            translation_error, rotation_error = transform_error(
                actual,
                expected_targets[name],
            )
            errors.append((translation_error, rotation_error, name))
        errors.sort(reverse=True)
        worst_translation = max(errors, key=lambda value: value[0])
        worst_rotation = max(errors, key=lambda value: value[1])
        if worst_translation[0] > 0.05 or worst_rotation[1] > 0.05:
            raise RuntimeError(
                "UEFN inverse FK verification failed: translation={} rotation={}".format(
                    worst_translation,
                    worst_rotation,
                )
            )

        report = {
            "sequence": sequence.get_path_name(),
            "frame": 0,
            "body_fk_track_left_active": body_section.is_active(),
            "uefn_track": new_track.get_path_name(),
            "uefn_apply_mode": str(
                unreal.ControlRigSequencerLibrary.get_fk_control_rig_apply_mode(
                    uefn_rig
                )
            ),
            "body_bone_count": len(body_bones),
            "uefn_bone_count": len(uefn_bone_keys),
            "shared_inverted_bone_count": len(shared),
            "keyed_control_count": len(keyed_controls),
            "worst_translation_error_cm": worst_translation,
            "worst_rotation_error_deg": worst_rotation,
            "sample_movement_cm": {
                name: movement.get(name)
                for name in (
                    "root",
                    "pelvis",
                    "head",
                    "hand_l",
                    "hand_r",
                    "foot_l",
                    "foot_r",
                )
            },
            "saved": False,
        }
        report_path = os.path.join(
            unreal.Paths.project_dir(),
            "Saved",
            "BlenderExchange",
            "InverseFK_UEFN_UnrealAudit.json",
        )
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
        print("INVERSE_FK_UEFN=" + json.dumps(report, sort_keys=True))
    except Exception:
        if created_track and new_track is not None:
            try:
                uefn_binding.remove_track(new_track)
                unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
            except Exception as rollback_error:
                unreal.log_error("Inverse FK rollback failed: {}".format(rollback_error))
        raise


main()
