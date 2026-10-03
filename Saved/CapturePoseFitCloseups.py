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
    ("Slide", ANIM_ROOT + "Slide/M_Neutral_Slide_KneesOut_Loop", 0.45),
    ("CliffCatch", ANIM_ROOT + "Traversal/Catch/Cliff/M_Neutral_Traversal_Catch_Cliff_high_stand", 0.8),
]
BODY_ASSET = None
SHOT_PREFIX = "MetaHuman_PoseFit_Close"

for arg in sys.argv[1:]:
    if arg.startswith("--body="):
        BODY_ASSET = arg.split("=", 1)[1]
    elif arg.startswith("--prefix="):
        SHOT_PREFIX = arg.split("=", 1)[1]

BODY_CODE = r'''
import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
meta_actor = next(a for a in actors if a.get_actor_label() == "MetaHuman_Far_Audit")
body = next(c for c in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == "Body")
body.set_skeletal_mesh_asset(unreal.load_asset(__BODY__))
print("CLOSEUP_BODY|" + body.get_skinned_asset().get_name())
'''

POSE_CODE = r'''
import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
uefn_actor = next(a for a in actors if a.get_actor_label() == "UEFN_Far_Audit")
meta_actor = next(a for a in actors if a.get_actor_label() == "MetaHuman_Far_Audit")
uefn_component = uefn_actor.skeletal_mesh_component
body = next(c for c in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == "Body")
lod_sync = next(c for c in meta_actor.get_components_by_class(unreal.ActorComponent) if c.get_name() == "LODSync")
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
lod_sync.set_editor_property("forced_lod", 0)
print("CLOSEUP_POSE_SET")
'''

CAPTURE_CODE = r'''
import os
import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
meta_actor = next(a for a in actors if a.get_actor_label() == "MetaHuman_Far_Audit")
body = next(c for c in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == "Body")

hand = body.get_socket_transform(__BONE__, unreal.RelativeTransformSpace.RTS_WORLD).translation
camera_pos = unreal.Vector(hand.x + __OFF_X__, hand.y + __OFF_Y__, hand.z + __OFF_Z__)
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
print("CLOSEUP_SHOT|" + path)
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
        if BODY_ASSET:
            print(run(remote, BODY_CODE.replace("__BODY__", repr(BODY_ASSET))).strip())
            time.sleep(1.0)
        for pose_name, anim, sample_time in POSES:
            run(remote, POSE_CODE.replace("__ANIM__", repr(anim)).replace("__TIME__", repr(sample_time)))
            time.sleep(2.0)
            for bone, off in (("hand_l", (60.0, 25.0, 12.0)), ("hand_r", (60.0, -25.0, 12.0))):
                filename = "{}_{}_{}.png".format(SHOT_PREFIX, pose_name, bone)
                code = (
                    CAPTURE_CODE.replace("__BONE__", repr(bone))
                    .replace("__OFF_X__", repr(off[0]))
                    .replace("__OFF_Y__", repr(off[1]))
                    .replace("__OFF_Z__", repr(off[2]))
                    .replace("__FILENAME__", repr(filename))
                )
                print(run(remote, code).strip().splitlines()[-1])
                time.sleep(3.0)
    finally:
        remote.stop()
    print("CLOSEUP_COMPLETE")


if __name__ == "__main__":
    main()
