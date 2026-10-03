import sys
import time

REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)

import remote_execution

ANIM_ROOT = "/Game/Characters/UEFN_Mannequin/Animations/"
POSES = [
    ("DemandingClimb", ANIM_ROOT + "Traversal/Climb/M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot", 2.0),
    ("CliffCatch", ANIM_ROOT + "Traversal/Catch/Cliff/M_Neutral_Traversal_Catch_Cliff_high_stand", 0.8),
    ("Sprint", ANIM_ROOT + "Sprint/M_Neutral_Sprint_Loop_F_L_20", 0.28),
    ("Slide", ANIM_ROOT + "Slide/M_Neutral_Slide_KneesOut_Loop", 0.45),
    ("Idle", ANIM_ROOT + "Idle/M_Neutral_Stand_Idle_Loop", 1.0),
]

SETUP_CODE = r'''
import unreal

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in subsystem.get_all_level_actors():
    label = actor.get_actor_label()
    if label.startswith("Reduced78_Audit") or label.startswith("UEFN_Ref_Audit"):
        subsystem.destroy_actor(actor)

body_mesh = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFN78_Body")
mann_mesh = unreal.load_asset("/Game/_mygame/SKM_UEFN_Mannequin")

reduced = subsystem.spawn_actor_from_class(
    unreal.SkeletalMeshActor, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator())
reduced.set_actor_label("Reduced78_Audit")
reduced.skeletal_mesh_component.set_skeletal_mesh_asset(body_mesh)

mann = subsystem.spawn_actor_from_class(
    unreal.SkeletalMeshActor, unreal.Vector(0.0, 120.0, 0.0), unreal.Rotator())
mann.set_actor_label("UEFN_Ref_Audit")
mann.skeletal_mesh_component.set_skeletal_mesh_asset(mann_mesh)

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "r.MotionBlurQuality 0")
unreal.SystemLibrary.execute_console_command(world, "r.ScreenPercentage 100")
print("AUDIT_SETUP_OK")
'''

POSE_CODE = r'''
import unreal

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
reduced = next(a for a in actors if a.get_actor_label() == "Reduced78_Audit")
mann = next(a for a in actors if a.get_actor_label() == "UEFN_Ref_Audit")
animation = unreal.load_asset(__ANIM__)
if not animation:
    raise RuntimeError("Missing anim " + __ANIM__)
for actor in (reduced, mann):
    component = actor.skeletal_mesh_component
    component.set_update_animation_in_editor(True)
    component.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
    )
    component.set_editor_property("forced_lod_model", 1)
    component.override_animation_data(animation, False, False, __TIME__, 0.0)
    component.set_position(__TIME__, False)
print("AUDIT_POSE_OK")
'''

CAPTURE_CODE = r'''
import math
import os
import unreal

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
reduced = next(a for a in actors if a.get_actor_label() == "Reduced78_Audit")
component = reduced.skeletal_mesh_component

target_name = __TARGET__
if target_name == "full":
    head = component.get_socket_location("head")
    pelvis = component.get_socket_location("pelvis")
    center = unreal.Vector((head.x + pelvis.x) / 2, (head.y + pelvis.y) / 2, (head.z + pelvis.z) / 2)
    offset = unreal.Vector(220.0, -160.0, 30.0)
    camera_pos = unreal.Vector(center.x + offset.x, center.y + offset.y, center.z + offset.z)
else:
    hand = component.get_socket_location(target_name)
    lower = component.get_socket_location(target_name.replace("hand", "lowerarm"))
    center = hand
    axis = unreal.Vector(hand.x - lower.x, hand.y - lower.y, hand.z - lower.z)
    length = math.sqrt(axis.x ** 2 + axis.y ** 2 + axis.z ** 2) or 1.0
    axis = unreal.Vector(axis.x / length, axis.y / length, axis.z / length)
    side = unreal.Vector(-axis.y, axis.x, 0.0)
    slen = math.sqrt(side.x ** 2 + side.y ** 2) or 1.0
    side = unreal.Vector(side.x / slen * 55.0, side.y / slen * 55.0, 18.0)
    camera_pos = unreal.Vector(hand.x + side.x, hand.y + side.y, hand.z + side.z)

rotation = unreal.MathLibrary.find_look_at_rotation(camera_pos, center)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_pos, rotation)
path = os.path.join(unreal.Paths.project_saved_dir(), "CodexLiveShots", __FILENAME__)
os.makedirs(os.path.dirname(path), exist_ok=True)
unreal.AutomationLibrary.finish_loading_before_screenshot()
try:
    unreal.AutomationLibrary.take_high_res_screenshot(1800, 1400, path)
except TypeError:
    unreal.AutomationLibrary.take_high_res_screenshot(
        1800, 1400, path, None, False, False,
        unreal.ComparisonTolerance.LOW, __FILENAME__, 0.1, True,
    )
print("AUDIT_SHOT|" + path)
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
            raise RuntimeError("No Unreal remote-execution node discovered")
        remote.open_command_connection(remote.remote_nodes[0]["node_id"])
        print(run(remote, SETUP_CODE).strip())
        time.sleep(1.0)
        for pose_name, anim, sample_time in POSES:
            run(remote, POSE_CODE.replace("__ANIM__", repr(anim)).replace("__TIME__", repr(sample_time)))
            time.sleep(2.0)
            for target in ("full", "hand_r", "hand_l"):
                filename = "Reduced78_{}_{}.png".format(pose_name, target)
                output = run(
                    remote,
                    CAPTURE_CODE.replace("__TARGET__", repr(target)).replace("__FILENAME__", repr(filename)),
                )
                marker = next(l for l in output.splitlines() if l.startswith("AUDIT_SHOT"))
                print("{} {}".format(pose_name, marker))
                time.sleep(2.5)
    finally:
        remote.stop()
    print("REDUCED_AUDIT_COMPLETE")


if __name__ == "__main__":
    main()
