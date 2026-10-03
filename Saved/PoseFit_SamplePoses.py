import json
import os

import unreal

SOURCE_BODY = "/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh"
UEFN_SKELETON = "/Game/_mygame/SK_UEFN_Mannequin"
ACTOR_LABEL = "ProphecySourceHelperProbe"
OUTPUT = os.path.join(unreal.Paths.project_saved_dir(), "PoseFit", "pose_samples.json")

ANIM_ROOT = "/Game/Characters/UEFN_Mannequin/Animations/"
POSE_SET = [
    ("Traversal/Climb/M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot", (0.4, 0.9, 1.4, 1.8, 2.2, 2.6, 3.1, 3.6)),
    ("Traversal/Climb/M_Relaxed_Traversal_Climb_Start_2_5_stand_F_Rfoot", (0.5, 1.2, 2.0, 2.8)),
    ("Sprint/M_Neutral_Sprint_Loop_F_L_20", (0.05, 0.2, 0.35, 0.5)),
    ("Idle/M_Neutral_Stand_Idle_Loop", (0.5, 2.0)),
    ("Idle/M_Relaxed_Stand_Idle_Loop", (1.0, 3.0)),
    ("Crouch/M_Neutral_Crouch_Loop_F", (0.2, 0.6)),
    ("Slide/M_Neutral_Slide_KneesOut_Loop", (0.2, 0.6, 1.0)),
    ("Slide/M_Neutral_Slide_FootOut_Loop", (0.3, 0.8)),
    ("Jump/M_Neutral_Jump_F_Land_Sprint_Heavy_Lfoot", (0.1, 0.35, 0.7)),
    ("Jump/M_Neutral_Jump_B_Start_Lfoot", (0.1, 0.3)),
    ("Traversal/Vault/M_Neutral_Traversal_Vault_1_0_run_F_Lfoot", (0.2, 0.5, 0.8, 1.1)),
    ("Traversal/Mantle/M_Neutral_Traversal_Mantle_1_0_run_F_Lfoot", (0.2, 0.6, 1.0, 1.4)),
    ("Traversal/Hurdle/M_Neutral_Traversal_Hurdle_1_0_run_F_Lfoot", (0.2, 0.5, 0.8)),
    ("Traversal/Catch/Cliff/M_Neutral_Traversal_Catch_Cliff_high_stand", (0.2, 0.6, 1.0)),
    ("Poses/M_Neutral_Sprint_Pose_Lean_L_hold", (0.1,)),
    ("Poses/M_Neutral_Run_Lean_Pose_Right", (0.1,)),
    ("Walk/M_Neutral_Walk_Loop_F", (0.2, 0.6)),
    ("Run/M_Neutral_Run_Loop_F", (0.1, 0.4)),
]

body = unreal.load_asset(SOURCE_BODY)
uefn_skeleton = unreal.load_asset(UEFN_SKELETON)
mh_skeleton = body.get_editor_property("skeleton")
compat = list(mh_skeleton.get_editor_property("compatible_skeletons"))
if not any(entry and entry.get_name() == "SK_UEFN_Mannequin" for entry in compat):
    compat.append(uefn_skeleton)
    mh_skeleton.set_editor_property("compatible_skeletons", compat)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
probe = None
for actor in actor_subsystem.get_all_level_actors():
    if actor.get_actor_label() == ACTOR_LABEL:
        probe = actor
        break
if probe is None:
    probe = actor_subsystem.spawn_actor_from_class(
        unreal.SkeletalMeshActor, unreal.Vector(0.0, 400.0, 0.0), unreal.Rotator()
    )
    probe.set_actor_label(ACTOR_LABEL)
component = probe.skeletal_mesh_component
component.set_skeletal_mesh_asset(body)
component.set_update_animation_in_editor(True)

with open(
    os.path.join(unreal.Paths.project_saved_dir(), "PoseFit", "record_bones.json"),
    "r",
    encoding="utf-8",
) as handle:
    record_bones = json.load(handle)

samples = []
previous_probe = None
for rel_path, times in POSE_SET:
    animation = unreal.load_asset(ANIM_ROOT + rel_path)
    if not animation:
        raise RuntimeError("Missing animation: " + rel_path)
    for sample_time in times:
        component.override_animation_data(animation, False, False, sample_time, 0.0)
        bones = {}
        for bone_name in record_bones:
            transform = component.get_socket_transform(
                bone_name, unreal.RelativeTransformSpace.RTS_COMPONENT
            )
            translation = transform.translation
            rotation = transform.rotation
            scale = transform.scale3d
            bones[bone_name] = [
                translation.x, translation.y, translation.z,
                rotation.x, rotation.y, rotation.z, rotation.w,
                scale.x, scale.y, scale.z,
            ]
        probe_value = bones["hand_l"][:3] + bones["thigh_r"][3:7]
        if previous_probe is not None and probe_value == previous_probe:
            raise RuntimeError(
                "Pose did not change for {} t={}; synchronous evaluation failed".format(
                    rel_path, sample_time
                )
            )
        previous_probe = probe_value
        samples.append({"anim": rel_path, "time": sample_time, "bones": bones})

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as handle:
    json.dump({"samples": samples, "record_bones": record_bones}, handle)
print("POSE_SAMPLES_DONE|count={}|output={}".format(len(samples), OUTPUT))
