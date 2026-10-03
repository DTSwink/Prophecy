import sys
import time

REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)

import remote_execution

TEST_BODY = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody_PoseFitTest"
ANIM_ROOT = "/Game/Characters/UEFN_Mannequin/Animations/"

# (pose name, animation, time)
POSES = [
    ("PoseFitDemandingClimb", ANIM_ROOT + "Traversal/Climb/M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot", 2.0),
    ("PoseFitSprint", ANIM_ROOT + "Sprint/M_Neutral_Sprint_Loop_F_L_20", 0.28),
    ("PoseFitSlide", ANIM_ROOT + "Slide/M_Neutral_Slide_KneesOut_Loop", 0.45),
    ("PoseFitCliffCatch", ANIM_ROOT + "Traversal/Catch/Cliff/M_Neutral_Traversal_Catch_Cliff_high_stand", 0.8),
]

SETUP_CODE = r'''
import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
uefn_actor = next(a for a in actors if a.get_actor_label() == "UEFN_Far_Audit")
meta_actor = next(a for a in actors if a.get_actor_label() == "MetaHuman_Far_Audit")
body = next(c for c in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == "Body")
face = next(c for c in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == "Face")
test_body = unreal.load_asset(__TEST_BODY__)
body.set_skeletal_mesh_asset(test_body)
if face.get_attach_parent() != body:
    raise RuntimeError("MetaHuman face is not attached to Body")

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "r.MotionBlurQuality 0")
unreal.SystemLibrary.execute_console_command(world, "r.ScreenPercentage 100")
unreal.EditorLevelLibrary.set_level_viewport_camera_info(
    unreal.Vector(220.0, 0.0, 108.0),
    unreal.Rotator(pitch=0.0, yaw=180.0, roll=0.0),
)
print("POSEFIT_AUDIT_SETUP|body=" + body.get_skinned_asset().get_name())
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
if not animation:
    raise RuntimeError("Missing animation: " + __ANIM__)

for component in (uefn_component, body):
    component.set_update_animation_in_editor(True)
    component.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
    )
    component.override_animation_data(animation, False, False, __TIME__, 0.0)
    component.set_position(__TIME__, False)

if __LOD_MODE__ == "LOD0":
    uefn_component.set_editor_property("forced_lod_model", 1)
    lod_sync.set_editor_property("forced_lod", 0)
else:
    uefn_component.set_editor_property("forced_lod_model", 0)
    lod_sync.set_editor_property("forced_lod", -1)
print("POSEFIT_AUDIT_POSE_SET")
'''

CAPTURE_CODE = r'''
import math
import os
import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
uefn_actor = next(a for a in actors if a.get_actor_label() == "UEFN_Far_Audit")
meta_actor = next(a for a in actors if a.get_actor_label() == "MetaHuman_Far_Audit")
uefn_component = uefn_actor.skeletal_mesh_component
body = next(c for c in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == "Body")
face = next(c for c in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == "Face")

max_t = 0.0
worst_bone = None
for bone_name in ("hand_l", "hand_r", "lowerarm_l", "lowerarm_r", "foot_l", "foot_r", "head", "pelvis", "spine_03"):
    s = uefn_component.get_socket_transform(bone_name, unreal.RelativeTransformSpace.RTS_COMPONENT)
    t = body.get_socket_transform(bone_name, unreal.RelativeTransformSpace.RTS_COMPONENT)
    d = s.translation - t.translation
    dt = math.sqrt(d.x * d.x + d.y * d.y + d.z * d.z)
    if dt > max_t:
        max_t = dt
        worst_bone = bone_name

body_head = body.get_socket_transform("head", unreal.RelativeTransformSpace.RTS_WORLD).translation
face_head = face.get_socket_transform("head", unreal.RelativeTransformSpace.RTS_WORLD).translation
hd = body_head - face_head
head_delta = math.sqrt(hd.x * hd.x + hd.y * hd.y + hd.z * hd.z)

path = os.path.join(unreal.Paths.project_saved_dir(), "CodexLiveShots", __FILENAME__)
os.makedirs(os.path.dirname(path), exist_ok=True)
unreal.AutomationLibrary.finish_loading_before_screenshot()
try:
    unreal.AutomationLibrary.take_high_res_screenshot(2200, 1375, path)
except TypeError:
    unreal.AutomationLibrary.take_high_res_screenshot(
        2200, 1375, path, None, False, False,
        unreal.ComparisonTolerance.LOW, __FILENAME__, 0.1, True,
    )
print("POSEFIT_AUDIT_VERIFY|max_t_cm={:.5f}|worst={}|face_head_cm={:.5f}|shot={}".format(
    max_t, worst_bone, head_delta, path))
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
        print(run(remote, SETUP_CODE.replace("__TEST_BODY__", repr(TEST_BODY))).strip())
        time.sleep(1.0)
        for pose_name, anim, sample_time in POSES:
            for lod_mode in ("LOD0", "Auto"):
                pose_code = (
                    POSE_CODE.replace("__ANIM__", repr(anim))
                    .replace("__TIME__", repr(sample_time))
                    .replace("__LOD_MODE__", repr(lod_mode))
                )
                run(remote, pose_code)
                time.sleep(2.0)
                filename = "MetaHuman_PoseFit_{}_{}.png".format(pose_name, lod_mode)
                capture_code = (
                    CAPTURE_CODE.replace("__FILENAME__", repr(filename))
                )
                output = run(remote, capture_code)
                marker = next(l for l in output.splitlines() if l.startswith("POSEFIT_AUDIT_VERIFY"))
                print("{} {} {}".format(pose_name, lod_mode, marker))
                time.sleep(3.0)
    finally:
        remote.stop()
    print("POSEFIT_AUDIT_COMPLETE")


if __name__ == "__main__":
    main()
