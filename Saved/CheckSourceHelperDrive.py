import json
import math
import os

import unreal

SOURCE_BODY = "/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh"
UEFN_SKELETON = "/Game/_mygame/SK_UEFN_Mannequin"
CLIMB = (
    "/Game/Characters/UEFN_Mannequin/Animations/Traversal/Climb/"
    "M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot"
)
ACTOR_LABEL = "ProphecySourceHelperProbe"

body = unreal.load_asset(SOURCE_BODY)
uefn_skeleton = unreal.load_asset(UEFN_SKELETON)
animation = unreal.load_asset(CLIMB)
if not body or not uefn_skeleton or not animation:
    raise RuntimeError("Missing source body, UEFN skeleton, or climb animation")

mh_skeleton = body.get_editor_property("skeleton")
compat = list(mh_skeleton.get_editor_property("compatible_skeletons"))
names = [entry.get_name() if entry else "" for entry in compat]
if "SK_UEFN_Mannequin" not in names:
    compat.append(uefn_skeleton)
    mh_skeleton.set_editor_property("compatible_skeletons", compat)
    print("COMPAT|added UEFN skeleton to metahuman_base_skel compatible list (in-memory)")
else:
    print("COMPAT|already compatible")

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
component.override_animation_data(animation, False, False, 2.0, 0.0)
print("PROBE|actor={}|mesh={}".format(probe.get_actor_label(), body.get_name()))

snapshot_path = os.path.join(
    unreal.Paths.project_dir(), "Tools", "MetaHuman", "skeleton_snapshots.json"
)
with open(snapshot_path, "r", encoding="utf-8") as handle:
    snapshot = json.load(handle)
mh_bones = snapshot["fitted_metahuman_body_reference"]["bones"]
ref_local = {b["name"]: b["local"] for b in mh_bones}
parent_of = {b["name"]: b["parent"] for b in mh_bones}

PROBE_BONES = [
    "hand_l", "lowerarm_l", "lowerarm_twist_01_l",
    "wrist_inner_l", "wrist_outer_l",
    "lowerarm_in_l", "lowerarm_out_l",
    "upperarm_twistCor_01_l", "thigh_twistCor_02_l",
    "index_02_half_l", "calf_knee_l",
    "clavicle_pec_l", "ankle_fwd_l",
]


def quat_angle_deg(q0, q1):
    dot = abs(q0[0] * q1[0] + q0[1] * q1[1] + q0[2] * q1[2] + q0[3] * q1[3])
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, dot))))


for name in PROBE_BONES:
    current = component.get_socket_transform(name, unreal.RelativeTransformSpace.RTS_COMPONENT)
    parent_name = parent_of.get(name)
    if parent_name:
        parent = component.get_socket_transform(parent_name, unreal.RelativeTransformSpace.RTS_COMPONENT)
        local = current * parent.inverse()
    else:
        local = current
    ref = ref_local[name]
    ref_t = ref["translation_cm"]
    ref_q = ref["rotation_xyzw"]
    dt = (
        (local.translation.x - ref_t[0]) ** 2
        + (local.translation.y - ref_t[1]) ** 2
        + (local.translation.z - ref_t[2]) ** 2
    ) ** 0.5
    lq = local.rotation
    dr = quat_angle_deg((lq.x, lq.y, lq.z, lq.w), tuple(ref_q))
    print("HELPER_DRIVE|{}|parent={}|local_dt_cm={:.4f}|local_dr_deg={:.4f}".format(
        name, parent_name, dt, dr))
