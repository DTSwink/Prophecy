"""Capture focused LOD0 audits of the Blender-reduced body in Unreal."""

import sys
import time


REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)
import remote_execution


ANIM_ROOT = "/Game/Characters/UEFN_Mannequin/Animations/"
POSES = (
    (
        "DemandingClimb",
        ANIM_ROOT
        + "Traversal/Climb/M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot",
        2.0,
        ("full", "wrist_r", "ankle_r"),
    ),
    (
        "CliffCatch",
        ANIM_ROOT
        + "Traversal/Catch/Cliff/M_Neutral_Traversal_Catch_Cliff_high_stand",
        0.8,
        ("wrist_r", "ankle_r"),
    ),
    (
        "Slide",
        ANIM_ROOT + "Slide/M_Neutral_Slide_KneesOut_Loop",
        0.45,
        ("wrist_r", "ankle_r"),
    ),
    (
        "Sprint",
        ANIM_ROOT + "Sprint/M_Neutral_Sprint_Loop_F_L_20",
        0.28,
        ("full", "wrist_r", "ankle_r"),
    ),
)


SETUP_CODE = r'''
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in subsystem.get_all_level_actors():
    if actor.get_actor_label() == "BlenderBody_Audit":
        subsystem.destroy_actor(actor)
mesh = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFNBlenderBodyTest")
if not isinstance(mesh, unreal.SkeletalMesh):
    raise RuntimeError("Missing Blender body test asset")
actor = subsystem.spawn_actor_from_class(
    unreal.SkeletalMeshActor,
    unreal.Vector(0.0, 0.0, -5000.0),
    unreal.Rotator(),
)
actor.set_actor_label("BlenderBody_Audit")
component = actor.skeletal_mesh_component
component.set_skeletal_mesh_asset(mesh)
component.set_update_animation_in_editor(True)
component.set_editor_property(
    "visibility_based_anim_tick_option",
    unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
)
component.set_editor_property("forced_lod_model", 1)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "r.MotionBlurQuality 0")
unreal.SystemLibrary.execute_console_command(world, "r.ScreenPercentage 100")
print("BLENDER_AUDIT_SETUP")
'''


POSE_CODE = r'''
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = next(
    actor for actor in subsystem.get_all_level_actors()
    if actor.get_actor_label() == "BlenderBody_Audit"
)
animation = unreal.load_asset(__ANIM__)
if animation is None:
    raise RuntimeError("Missing animation: " + __ANIM__)
component = actor.skeletal_mesh_component
component.override_animation_data(animation, False, False, __TIME__, 0.0)
component.set_position(__TIME__, False)
print("BLENDER_AUDIT_POSE")
'''


CAPTURE_CODE = r'''
import math
import os
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = next(
    actor for actor in subsystem.get_all_level_actors()
    if actor.get_actor_label() == "BlenderBody_Audit"
)
component = actor.skeletal_mesh_component
target_name = __TARGET__
if target_name == "full":
    head = component.get_socket_location("head")
    pelvis = component.get_socket_location("pelvis")
    center = unreal.Vector(
        (head.x + pelvis.x) * 0.5,
        (head.y + pelvis.y) * 0.5,
        (head.z + pelvis.z) * 0.5,
    )
    camera_pos = unreal.Vector(center.x + 220.0, center.y - 160.0, center.z + 30.0)
else:
    if target_name == "wrist_r":
        parent_name, child_name, distance = "lowerarm_r", "hand_r", 55.0
    elif target_name == "ankle_r":
        parent_name, child_name, distance = "calf_r", "foot_r", 70.0
    else:
        raise RuntimeError("Unknown target " + target_name)
    parent = component.get_socket_location(parent_name)
    child = component.get_socket_location(child_name)
    axis = unreal.Vector(child.x - parent.x, child.y - parent.y, child.z - parent.z)
    length = math.sqrt(axis.x ** 2 + axis.y ** 2 + axis.z ** 2) or 1.0
    axis = unreal.Vector(axis.x / length, axis.y / length, axis.z / length)
    side = unreal.Vector(-axis.y, axis.x, 0.0)
    side_length = math.sqrt(side.x ** 2 + side.y ** 2) or 1.0
    side = unreal.Vector(side.x / side_length, side.y / side_length, 0.0)
    center = unreal.Vector(
        child.x - axis.x,
        child.y - axis.y,
        child.z - axis.z,
    )
    camera_pos = unreal.Vector(
        center.x + side.x * distance,
        center.y + side.y * distance,
        center.z + 12.0,
    )
rotation = unreal.MathLibrary.find_look_at_rotation(camera_pos, center)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_pos, rotation)
path = os.path.join(unreal.Paths.project_saved_dir(), "CodexLiveShots", __FILENAME__)
unreal.AutomationLibrary.finish_loading_before_screenshot()
try:
    unreal.AutomationLibrary.take_high_res_screenshot(1800, 1400, path)
except TypeError:
    unreal.AutomationLibrary.take_high_res_screenshot(
        1800, 1400, path, None, False, False,
        unreal.ComparisonTolerance.LOW, __FILENAME__, 0.1, True,
    )
print("BLENDER_AUDIT_SHOT|" + path)
'''


CLEANUP_CODE = r'''
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in subsystem.get_all_level_actors():
    if actor.get_actor_label() == "BlenderBody_Audit":
        subsystem.destroy_actor(actor)
print("BLENDER_AUDIT_CLEANUP")
'''


def _run(remote, code):
    result = remote.run_command(
        code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE
    )
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
            raise RuntimeError("No Unreal remote-execution node discovered")
        remote.open_command_connection(remote.remote_nodes[0]["node_id"])
        print(_run(remote, SETUP_CODE).strip())
        time.sleep(1.0)
        for pose_name, animation, sample_time, targets in POSES:
            _run(
                remote,
                POSE_CODE.replace("__ANIM__", repr(animation)).replace(
                    "__TIME__", repr(sample_time)
                ),
            )
            time.sleep(1.5)
            for target in targets:
                filename = "BlenderBody_{}_{}_LOD0.png".format(pose_name, target)
                output = _run(
                    remote,
                    CAPTURE_CODE.replace("__TARGET__", repr(target)).replace(
                        "__FILENAME__", repr(filename)
                    ),
                )
                print(
                    next(
                        line
                        for line in output.splitlines()
                        if line.startswith("BLENDER_AUDIT_SHOT")
                    )
                )
                time.sleep(2.5)
        print(_run(remote, CLEANUP_CODE).strip())
    finally:
        remote.stop()
    print("BLENDER_BODY_AUDIT_DONE")


if __name__ == "__main__":
    main()
