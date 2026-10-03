import sys
import time

REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)

import remote_execution

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

SETUP_CODE = r'''
import json
import os
import unreal

SOURCE_BODY = "/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh"
UEFN_SKELETON = "/Game/_mygame/SK_UEFN_Mannequin"
ACTOR_LABEL = "ProphecySourceHelperProbe"

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

performance_settings = unreal.load_object(
    None, "/Script/UnrealEd.Default__EditorPerformanceSettings"
)
if performance_settings:
    for property_name in (
        "throttle_cpu_when_not_foreground",
        "b_throttle_cpu_when_not_foreground",
    ):
        try:
            performance_settings.set_editor_property(property_name, False)
            print("POSEFIT_THROTTLE|disabled via " + property_name)
            break
        except Exception:
            pass

samples_path = os.path.join(unreal.Paths.project_saved_dir(), "PoseFit", "pose_samples.jsonl")
os.makedirs(os.path.dirname(samples_path), exist_ok=True)
with open(samples_path, "w", encoding="utf-8") as handle:
    handle.write("")
print("POSEFIT_SETUP_DONE")
'''

POSE_CODE = r'''
import unreal

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()
probe = next(a for a in actors if a.get_actor_label() == "ProphecySourceHelperProbe")
uefn = next(a for a in actors if a.get_actor_label() == "UEFN_Far_Audit")
animation = unreal.load_asset(__ANIM__)
if not animation:
    raise RuntimeError("Missing animation " + __ANIM__)
for component in (probe.skeletal_mesh_component, uefn.skeletal_mesh_component):
    component.set_update_animation_in_editor(True)
    component.set_editor_property("forced_lod_model", 1)
    component.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
    )
    component.override_animation_data(animation, False, False, __TIME__, 0.0)
    component.set_position(__TIME__, False)
print("POSEFIT_POSE_SET")
'''

PROBE_CODE = r'''
import unreal

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()
probe = next(a for a in actors if a.get_actor_label() == "ProphecySourceHelperProbe")
uefn = next(a for a in actors if a.get_actor_label() == "UEFN_Far_Audit")
values = []
for component in (probe.skeletal_mesh_component, uefn.skeletal_mesh_component):
    for bone in ("hand_l", "hand_r", "foot_l", "spine_03", "head"):
        transform = component.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_COMPONENT)
        t = transform.translation
        q = transform.rotation
        values += [t.x, t.y, t.z, q.x, q.y, q.z, q.w]
print("POSEFIT_PROBE|" + "|".join("{:.6f}".format(v) for v in values))
'''

RECORD_CODE = r'''
import json
import os
import unreal

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()
probe = next(a for a in actors if a.get_actor_label() == "ProphecySourceHelperProbe")
uefn = next(a for a in actors if a.get_actor_label() == "UEFN_Far_Audit")

with open(
    os.path.join(unreal.Paths.project_saved_dir(), "PoseFit", "record_bones.json"),
    "r", encoding="utf-8",
) as handle:
    record_bones = json.load(handle)

def read_bones(component, names):
    bones = {}
    for bone_name in names:
        transform = component.get_socket_transform(bone_name, unreal.RelativeTransformSpace.RTS_COMPONENT)
        t = transform.translation
        q = transform.rotation
        s = transform.scale3d
        bones[bone_name] = [t.x, t.y, t.z, q.x, q.y, q.z, q.w, s.x, s.y, s.z]
    return bones


mh_bones = read_bones(probe.skeletal_mesh_component, record_bones)
uefn_names = [n for n in record_bones if uefn.skeletal_mesh_component.get_bone_index(n) != -1]
uefn_bones = read_bones(uefn.skeletal_mesh_component, uefn_names)

samples_path = os.path.join(unreal.Paths.project_saved_dir(), "PoseFit", "pose_samples.jsonl")
with open(samples_path, "a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "anim": __ANIM__, "time": __TIME__,
        "bones": mh_bones, "uefn_bones": uefn_bones,
    }) + "\n")
probe_values = mh_bones["hand_l"][:3] + mh_bones["thigh_r"][3:7] + uefn_bones["hand_l"][:3]
print("POSEFIT_RECORDED|" + "|".join("{:.6f}".format(v) for v in probe_values))
'''


def run(remote, code):
    result = remote.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
    output = "".join(entry.get("output", "") for entry in result.get("output", []))
    if not result.get("success"):
        raise RuntimeError(result.get("result", "Remote execution failed") + "\n" + output)
    return output


def main():
    remote = remote_execution.RemoteExecution()
    remote.start()
    try:
        deadline = time.monotonic() + 15.0
        while not remote.remote_nodes and time.monotonic() < deadline:
            time.sleep(0.25)
        if not remote.remote_nodes:
            raise RuntimeError("No Unreal remote-execution node was discovered")
        remote.open_command_connection(remote.remote_nodes[0]["node_id"])
        print(run(remote, SETUP_CODE).strip())
        previous_probe = None
        total = 0
        for rel_path, times in POSE_SET:
            anim = ANIM_ROOT + rel_path
            for raw_time in times:
                sample_time = raw_time + 0.0037 * (total % 7)

                def make_pose_code(value):
                    return POSE_CODE.replace("__ANIM__", repr(anim)).replace("__TIME__", repr(value))

                run(remote, make_pose_code(sample_time))
                marker = None
                for attempt in range(40):
                    time.sleep(0.5)
                    output = run(remote, PROBE_CODE)
                    candidate = next(l for l in output.splitlines() if l.startswith("POSEFIT_PROBE"))
                    if candidate != previous_probe:
                        marker = candidate
                        break
                    sample_time += 0.0011
                    run(remote, make_pose_code(sample_time))
                if marker is None:
                    raise RuntimeError("Pose did not advance at {} t={}".format(rel_path, sample_time))
                record_code = RECORD_CODE.replace("__ANIM__", repr(anim)).replace("__TIME__", repr(sample_time))
                run(remote, record_code)
                previous_probe = marker
                total += 1
                print("sampled {} t={}".format(rel_path, sample_time))
        print("POSEFIT_SAMPLING_COMPLETE|{}".format(total))
    finally:
        remote.stop()


if __name__ == "__main__":
    main()
