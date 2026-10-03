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
    ("CliffCatch", ANIM_ROOT + "Traversal/Catch/Cliff/M_Neutral_Traversal_Catch_Cliff_high_stand", 0.8),
    ("Climb", ANIM_ROOT + "Traversal/Climb/M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot", 2.0),
]

POSE_CODE = r'''
import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
probe = next(a for a in actors if a.get_actor_label() == "ProphecySourceHelperProbe")
compare = next(a for a in actors if a.get_actor_label() == "ProphecyPoseFitCompare")
animation = unreal.load_asset(__ANIM__)
for component in (probe.skeletal_mesh_component, compare.skeletal_mesh_component):
    component.set_update_animation_in_editor(True)
    component.set_editor_property("forced_lod_model", 1)
    component.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
    )
    component.override_animation_data(animation, False, False, __TIME__, 0.0)
    component.set_position(__TIME__, False)
print("ABC_POSE_SET")
'''

SHOT_CODE = r'''
import os
import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
if __USE_PROBE__:
    target = next(a for a in actors if a.get_actor_label() == "ProphecySourceHelperProbe").skeletal_mesh_component
else:
    target = next(a for a in actors if a.get_actor_label() == "ProphecyPoseFitCompare").skeletal_mesh_component

hand = target.get_socket_transform("hand_r", unreal.RelativeTransformSpace.RTS_WORLD).translation
camera_pos = unreal.Vector(hand.x + 45.0, hand.y - 20.0, hand.z + 10.0)
rotation = unreal.MathLibrary.find_look_at_rotation(camera_pos, hand)
unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(camera_pos, rotation)
path = os.path.join(unreal.Paths.project_saved_dir(), "CodexLiveShots", __FILENAME__)
unreal.AutomationLibrary.finish_loading_before_screenshot()
try:
    unreal.AutomationLibrary.take_high_res_screenshot(1600, 1000, path)
except TypeError:
    unreal.AutomationLibrary.take_high_res_screenshot(
        1600, 1000, path, None, False, False,
        unreal.ComparisonTolerance.LOW, __FILENAME__, 0.1, True,
    )
print("ABC_SHOT|" + path)
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
        for pose_name, anim, sample_time in POSES:
            run(remote, POSE_CODE.replace("__ANIM__", repr(anim)).replace("__TIME__", repr(sample_time)))
            time.sleep(2.0)
            for use_probe, label in ((True, "SourceFullRig"), (False, "PoseFitReduced")):
                filename = "MetaHuman_HandAB_{}_{}.png".format(pose_name, label)
                code = (
                    SHOT_CODE.replace("__USE_PROBE__", repr(use_probe))
                    .replace("__FILENAME__", repr(filename))
                )
                print(run(remote, code).strip().splitlines()[-1])
                time.sleep(3.0)
    finally:
        remote.stop()
    print("ABC_COMPLETE")


if __name__ == "__main__":
    main()
