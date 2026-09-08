"""Live-editor visual and transform audit for the imported Boss UEFN mesh."""

import json
import math
import os
import sys
import time
from pathlib import Path


REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)
import remote_execution


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
OUTPUT_DIR = PROJECT / "Saved" / "CodexLiveShots" / "BossUEFN"
AUDIT = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_UEFN_UnrealVisualAudit.json"
)
ANIM_ROOT = "/Game/Characters/UEFN_Mannequin/Animations/"
POSES = (
    (
        "Idle",
        ANIM_ROOT + "Idle/M_Neutral_Stand_Idle_Loop",
        1.0,
        ("Full",),
    ),
    (
        "Sprint",
        ANIM_ROOT + "Sprint/M_Neutral_Sprint_Loop_F_L_20",
        0.28,
        ("Full", "Neck", "WristR", "AnkleR"),
    ),
    (
        "Climb",
        ANIM_ROOT
        + "Traversal/Climb/M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot",
        2.0,
        ("Full", "Neck", "WristR", "AnkleR"),
    ),
    (
        "CliffCatch",
        ANIM_ROOT
        + "Traversal/Catch/Cliff/M_Neutral_Traversal_Catch_Cliff_high_stand",
        0.8,
        ("Full", "Neck"),
    ),
)

SETUP = r'''
import unreal

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in actor_subsystem.get_all_level_actors():
    if actor.get_actor_label() in ("BossUEFN_Audit", "BossUEFN_Reference"):
        actor_subsystem.destroy_actor(actor)

boss_mesh = unreal.load_asset(
    "/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN"
)
reference_mesh = unreal.load_asset("/Game/_mygame/SKM_UEFN_Mannequin")
if not isinstance(boss_mesh, unreal.SkeletalMesh):
    raise RuntimeError("Missing imported Boss UEFN Skeletal Mesh")
if not isinstance(reference_mesh, unreal.SkeletalMesh):
    raise RuntimeError("Missing UEFN mannequin reference mesh")

location = unreal.Vector(0.0, 0.0, -5000.0)
boss = actor_subsystem.spawn_actor_from_class(
    unreal.SkeletalMeshActor, location, unreal.Rotator()
)
boss.set_actor_label("BossUEFN_Audit")
boss.skeletal_mesh_component.set_skeletal_mesh_asset(boss_mesh)

reference = actor_subsystem.spawn_actor_from_class(
    unreal.SkeletalMeshActor, location, unreal.Rotator()
)
reference.set_actor_label("BossUEFN_Reference")
reference.skeletal_mesh_component.set_skeletal_mesh_asset(reference_mesh)

for component in (
    boss.skeletal_mesh_component,
    reference.skeletal_mesh_component,
):
    component.set_update_animation_in_editor(True)
    component.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
    )
    component.set_editor_property("forced_lod_model", 1)

world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "r.MotionBlurQuality 0")
unreal.SystemLibrary.execute_console_command(world, "r.ScreenPercentage 100")
unreal.SystemLibrary.execute_console_command(world, "ShowFlag.Grid 0")
print("BOSS_UEFN_AUDIT_SETUP")
'''

POSE = r'''
import json
import math
import unreal

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()
boss = next(
    actor for actor in actors if actor.get_actor_label() == "BossUEFN_Audit"
)
reference = next(
    actor for actor in actors if actor.get_actor_label() == "BossUEFN_Reference"
)
animation = unreal.load_asset(__ANIMATION__)
if animation is None:
    raise RuntimeError("Missing animation " + __ANIMATION__)
for actor in (boss, reference):
    component = actor.skeletal_mesh_component
    # `override_animation_data(..., is_playing=False, play_rate=0)` serializes
    # the requested time but does not force an immediate editor evaluation.
    # Drive the actual AnimSingleNodeInstance so the captured pose is the
    # requested animation sample, rather than the component's previous pose.
    component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    component.set_animation(animation)
    instance = component.get_anim_instance()
    if not isinstance(instance, unreal.AnimSingleNodeInstance):
        raise RuntimeError("Expected an AnimSingleNodeInstance")
    instance.set_animation_asset(animation, False, 0.0)
    instance.set_position(__TIME__, False)

probe_bones = (
    "pelvis", "spine_03", "spine_05", "neck_01", "neck_02", "head",
    "clavicle_l", "upperarm_l", "lowerarm_l", "hand_l",
    "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r",
    "thigh_l", "calf_l", "foot_l", "thigh_r", "calf_r", "foot_r",
)
maximum_translation = 0.0
maximum_rotation = 0.0
for bone in probe_bones:
    boss_transform = boss.skeletal_mesh_component.get_socket_transform(
        bone, unreal.RelativeTransformSpace.RTS_COMPONENT
    )
    reference_transform = reference.skeletal_mesh_component.get_socket_transform(
        bone, unreal.RelativeTransformSpace.RTS_COMPONENT
    )
    delta = boss_transform.translation - reference_transform.translation
    translation = math.sqrt(delta.x * delta.x + delta.y * delta.y + delta.z * delta.z)
    maximum_translation = max(maximum_translation, translation)
    left = boss_transform.rotation
    right = reference_transform.rotation
    dot = abs(left.x * right.x + left.y * right.y + left.z * right.z + left.w * right.w)
    dot = max(-1.0, min(1.0, dot))
    rotation = math.degrees(2.0 * math.acos(dot))
    maximum_rotation = max(maximum_rotation, rotation)
print(
    "BOSS_UEFN_POSE="
    + json.dumps(
        {
            "maximum_probe_bone_translation_delta_cm": maximum_translation,
            "maximum_probe_bone_rotation_delta_deg": maximum_rotation,
        },
        sort_keys=True,
    )
)
'''

CAPTURE = r'''
import math
import os
import unreal

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()
boss = next(
    actor for actor in actors if actor.get_actor_label() == "BossUEFN_Audit"
)
reference = next(
    actor for actor in actors if actor.get_actor_label() == "BossUEFN_Reference"
)
component = boss.skeletal_mesh_component
target = __TARGET__

if target == "Full":
    head = component.get_socket_location("head")
    pelvis = component.get_socket_location("pelvis")
    center = unreal.Vector(
        (head.x + pelvis.x) * 0.5,
        (head.y + pelvis.y) * 0.5,
        (head.z + pelvis.z) * 0.5,
    )
    camera = unreal.Vector(center.x, center.y + 315.0, center.z + 15.0)
elif target == "Neck":
    low = component.get_socket_location("spine_05")
    high = component.get_socket_location("head")
    center = unreal.Vector(
        (low.x + high.x) * 0.5,
        (low.y + high.y) * 0.5,
        (low.z + high.z) * 0.5,
    )
    camera = unreal.Vector(center.x, center.y + 115.0, center.z + 4.0)
elif target == "WristR":
    parent = component.get_socket_location("lowerarm_r")
    child = component.get_socket_location("hand_r")
    center = child
    axis = unreal.Vector(child.x-parent.x, child.y-parent.y, child.z-parent.z)
    length = math.sqrt(axis.x*axis.x + axis.y*axis.y + axis.z*axis.z) or 1.0
    side = unreal.Vector(-axis.y/length, axis.x/length, 0.0)
    side_length = math.sqrt(side.x*side.x + side.y*side.y) or 1.0
    camera = unreal.Vector(
        center.x + side.x/side_length*55.0,
        center.y + side.y/side_length*55.0,
        center.z + 15.0,
    )
elif target == "AnkleR":
    parent = component.get_socket_location("calf_r")
    child = component.get_socket_location("foot_r")
    center = child
    camera = unreal.Vector(center.x + 70.0, center.y - 50.0, center.z + 18.0)
else:
    raise RuntimeError("Unknown capture target " + target)

rotation = unreal.MathLibrary.find_look_at_rotation(camera, center)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera, rotation)
boss.skeletal_mesh_component.set_visibility(__BOSS_VISIBLE__, True)
reference.skeletal_mesh_component.set_visibility(not __BOSS_VISIBLE__, True)
path = __OUTPUT__
os.makedirs(os.path.dirname(path), exist_ok=True)
unreal.AutomationLibrary.finish_loading_before_screenshot()
try:
    unreal.AutomationLibrary.take_high_res_screenshot(1600, 1200, path)
except TypeError:
    unreal.AutomationLibrary.take_high_res_screenshot(
        1600, 1200, path, None, False, False,
        unreal.ComparisonTolerance.LOW, os.path.basename(path), 0.1, True,
    )
print("BOSS_UEFN_SHOT|" + path)
'''

CLEANUP = r'''
import unreal
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in actor_subsystem.get_all_level_actors():
    if actor.get_actor_label() in ("BossUEFN_Audit", "BossUEFN_Reference"):
        actor_subsystem.destroy_actor(actor)
print("BOSS_UEFN_AUDIT_CLEANUP")
'''


def run(remote, code):
    result = remote.run_command(
        code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE
    )
    output = "".join(
        entry.get("output", "") for entry in result.get("output", [])
    )
    if not result.get("success"):
        raise RuntimeError(result.get("result", "Remote execution failed") + output)
    return output


def connect():
    remote = remote_execution.RemoteExecution()
    remote.start()
    deadline = time.monotonic() + 30.0
    while not remote.remote_nodes and time.monotonic() < deadline:
        time.sleep(0.25)
    if not remote.remote_nodes:
        remote.stop()
        raise RuntimeError("No running Unreal remote node")
    remote.open_command_connection(remote.remote_nodes[0]["node_id"])
    return remote


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    remote = connect()
    report = {"poses": {}}
    try:
        print(run(remote, SETUP).strip())
        time.sleep(1.0)
        for label, animation, seconds, targets in POSES:
            pose_output = run(
                remote,
                POSE.replace("__ANIMATION__", repr(animation)).replace(
                    "__TIME__", repr(seconds)
                ),
            )
            marker = next(
                line.split("=", 1)[1]
                for line in pose_output.splitlines()
                if line.startswith("BOSS_UEFN_POSE=")
            )
            pose_report = json.loads(marker)
            pose_report.update(
                {
                    "animation": animation,
                    "sample_seconds": seconds,
                    "images": {},
                }
            )
            time.sleep(1.0)
            for target in targets:
                pose_report["images"][target] = {}
                for subject, boss_visible in (
                    ("Boss", True),
                    ("Mannequin", False),
                ):
                    output = OUTPUT_DIR / (
                        f"Unreal_{subject}_{label}_{target}.png"
                    )
                    code = (
                        CAPTURE.replace("__TARGET__", repr(target))
                        .replace("__BOSS_VISIBLE__", repr(boss_visible))
                        .replace("__OUTPUT__", repr(str(output)))
                    )
                    print(run(remote, code).strip())
                    deadline = time.monotonic() + 12.0
                    while not output.is_file() and time.monotonic() < deadline:
                        time.sleep(0.25)
                    if not output.is_file():
                        raise RuntimeError("Unreal screenshot was not created: " + str(output))
                    pose_report["images"][target][subject] = str(output)
            report["poses"][label] = pose_report
    finally:
        try:
            print(run(remote, CLEANUP).strip())
        except Exception as error:
            print("Boss animation audit cleanup failed: " + str(error))
        remote.stop()
    AUDIT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print("BOSS_UEFN_UNREAL_AUDIT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
