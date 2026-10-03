import sys
import time

REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)

import remote_execution

ANIM = (
    "/Game/Characters/UEFN_Mannequin/Animations/Traversal/Catch/Cliff/"
    "M_Neutral_Traversal_Catch_Cliff_high_stand"
)
TIME = 0.8

CODE = r'''
import os
import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
uefn_actor = next(a for a in actors if a.get_actor_label() == "UEFN_Far_Audit")
meta_actor = next(a for a in actors if a.get_actor_label() == "MetaHuman_Far_Audit")
uefn_component = uefn_actor.skeletal_mesh_component
body = next(c for c in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == "Body")
animation = unreal.load_asset(__ANIM__)
for component in (uefn_component, body):
    component.set_update_animation_in_editor(True)
    component.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
    )
    component.override_animation_data(animation, False, False, __TIME__, 0.0)
    component.set_position(__TIME__, False)
uefn_component.set_editor_property("forced_lod_model", 1)
print("REF_POSE_SET")
'''

SHOT_CODE = r'''
import os
import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
uefn_actor = next(a for a in actors if a.get_actor_label() == "UEFN_Far_Audit")
uefn_component = uefn_actor.skeletal_mesh_component
hand = uefn_component.get_socket_transform("hand_r", unreal.RelativeTransformSpace.RTS_WORLD).translation
camera_pos = unreal.Vector(hand.x + 60.0, hand.y - 25.0, hand.z + 12.0)
rotation = unreal.MathLibrary.find_look_at_rotation(camera_pos, hand)
unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(camera_pos, rotation)
path = os.path.join(unreal.Paths.project_saved_dir(), "CodexLiveShots", "UEFN_Reference_CliffCatch_hand_r.png")
unreal.AutomationLibrary.finish_loading_before_screenshot()
try:
    unreal.AutomationLibrary.take_high_res_screenshot(1600, 1000, path)
except TypeError:
    unreal.AutomationLibrary.take_high_res_screenshot(
        1600, 1000, path, None, False, False,
        unreal.ComparisonTolerance.LOW, "UEFN_Reference_CliffCatch_hand_r.png", 0.1, True,
    )
print("REF_SHOT|" + path)
'''


def run(remote, code):
    result = remote.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
    output = "".join(entry.get("output", "") for entry in result.get("output", []))
    if not result.get("success"):
        raise RuntimeError(result.get("result", "Remote execution failed") + "\n" + output)
    return output


remote = remote_execution.RemoteExecution()
remote.start()
try:
    deadline = time.monotonic() + 15.0
    while not remote.remote_nodes and time.monotonic() < deadline:
        time.sleep(0.25)
    if not remote.remote_nodes:
        raise RuntimeError("No Unreal remote-execution node was discovered")
    remote.open_command_connection(remote.remote_nodes[0]["node_id"])
    run(remote, CODE.replace("__ANIM__", repr(ANIM)).replace("__TIME__", repr(TIME)))
    time.sleep(2.0)
    print(run(remote, SHOT_CODE).strip().splitlines()[-1])
    time.sleep(3.0)
finally:
    remote.stop()
