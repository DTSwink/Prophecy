import os
import sys
import time


REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)

import remote_execution


SETUP_CODE = r'''
import os
import unreal

TAG = "CodexMetaHumanHandAudit"
editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in editor_actor_subsystem.get_all_level_actors():
    if TAG in [str(value) for value in actor.tags]:
        editor_actor_subsystem.destroy_actor(actor)

uefn_mesh = unreal.load_asset("/Game/_mygame/SKM_UEFN_Mannequin")
direct_mesh = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody_WeightTransferTest")
animation = unreal.load_asset("/Game/Characters/UEFN_Mannequin/Animations/Sprint/M_Neutral_Sprint_Loop_F_L_20")
if not uefn_mesh or not direct_mesh or not animation:
    raise RuntimeError("Missing audit mesh or animation")

def spawn(label, mesh, anim, y):
    actor = editor_actor_subsystem.spawn_actor_from_class(
        unreal.SkeletalMeshActor,
        unreal.Vector(0.0, y, 0.0),
        unreal.Rotator(pitch=0.0, yaw=-90.0, roll=0.0),
        False,
    )
    actor.tags = [TAG]
    actor.set_actor_label(label)
    component = actor.skeletal_mesh_component
    component.set_skeletal_mesh_asset(mesh)
    component.set_editor_property("forced_lod_model", 1)
    component.set_update_animation_in_editor(True)
    component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    component.play_animation(anim, False)
    component.set_position(0.0, False)
    component.set_play_rate(0.0)
    return actor

spawn("UEFN_Hand_Audit", uefn_mesh, animation, -62.0)
spawn("MetaHuman_Hand_Audit", direct_mesh, animation, 62.0)

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "r.MotionBlurQuality 0")
unreal.SystemLibrary.execute_console_command(world, "r.DefaultFeature.MotionBlur 0")
unreal.SystemLibrary.execute_console_command(world, "r.ScreenPercentage 100")
unreal.EditorLevelLibrary.set_level_viewport_camera_info(
    unreal.Vector(115.0, 0.0, 110.0),
    unreal.Rotator(pitch=0.0, yaw=180.0, roll=0.0),
)
print("HAND_AUDIT_SETUP_COMPLETE|sequence_length=" + str(animation.sequence_length))
'''


CAPTURE_CODE = r'''
import os
import unreal

sample_time = __SAMPLE_TIME__
tag = "CodexMetaHumanHandAudit"
editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
animation = unreal.load_asset("/Game/Characters/UEFN_Mannequin/Animations/Sprint/M_Neutral_Sprint_Loop_F_L_20")
for actor in editor_actor_subsystem.get_all_level_actors():
    if tag in [str(value) for value in actor.tags]:
        component = actor.skeletal_mesh_component
        component.play_animation(animation, False)
        component.set_position(sample_time, False)
        component.set_play_rate(0.0)

path = os.path.join(
    unreal.Paths.project_saved_dir(),
    "CodexLiveShots",
    "__FILENAME__",
)
os.makedirs(os.path.dirname(path), exist_ok=True)
unreal.AutomationLibrary.finish_loading_before_screenshot()
try:
    unreal.AutomationLibrary.take_high_res_screenshot(1600, 1000, path)
except TypeError:
    unreal.AutomationLibrary.take_high_res_screenshot(
        1600, 1000, path, None, False, False,
        unreal.ComparisonTolerance.LOW,
        "__FILENAME__", 0.1, True,
    )
print("HAND_AUDIT_SCREENSHOT=" + path)
'''


def run(remote, code):
    result = remote.run_command(
        code,
        unattended=True,
        exec_mode=remote_execution.MODE_EXEC_FILE,
    )
    if not result.get("success"):
        raise RuntimeError(result.get("result", "Remote execution failed"))
    for entry in result.get("output", []):
        print(entry.get("output", ""))


remote = remote_execution.RemoteExecution()
remote.start()
try:
    deadline = time.monotonic() + 15.0
    while not remote.remote_nodes and time.monotonic() < deadline:
        time.sleep(0.25)
    if not remote.remote_nodes:
        raise RuntimeError("No Unreal remote-execution node was discovered")
    remote.open_command_connection(remote.remote_nodes[0]["node_id"])
    run(remote, SETUP_CODE)
    time.sleep(3.0)
    for sample_time in (0.0, 0.5, 1.0, 1.5):
        time_token = f"{sample_time:.2f}".replace(".", "_")
        filename = f"MetaHuman_HandWeightTransfer_LOD0_t{time_token}.png"
        code = CAPTURE_CODE.replace("__SAMPLE_TIME__", repr(sample_time)).replace(
            "__FILENAME__", filename
        )
        run(remote, code)
        time.sleep(2.0)
finally:
    remote.stop()

print("HAND_AUDIT_SEQUENCE_CAPTURE_COMPLETE")
