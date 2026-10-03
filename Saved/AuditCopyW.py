import os
import sys
import time

REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)
import remote_execution

IMPORT_CODE = r'''
import os, unreal
EXCHANGE = os.path.join(unreal.Paths.project_dir(), "Saved", "BlenderExchange")
SKEL = "/Game/_mygame/SK_UEFN_Mannequin.SK_UEFN_Mannequin"
path = "/Game/_mygame/MetaHumans/SKM_test_UEFN78_CopyW"
if unreal.EditorAssetLibrary.does_asset_exist(path):
    unreal.EditorAssetLibrary.delete_asset(path)
options = unreal.FbxImportUI()
options.set_editor_property("import_mesh", True)
options.set_editor_property("import_as_skeletal", True)
options.set_editor_property("import_animations", False)
options.set_editor_property("import_materials", False)
options.set_editor_property("import_textures", False)
options.set_editor_property("create_physics_asset", False)
options.set_editor_property("skeleton", unreal.load_asset(SKEL))
options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
sm = options.get_editor_property("skeletal_mesh_import_data")
sm.set_editor_property("update_skeleton_reference_pose", False)
task = unreal.AssetImportTask()
task.set_editor_property("filename", os.path.join(EXCHANGE, "Body_UEFN_CopyW.fbx"))
task.set_editor_property("destination_path", "/Game/_mygame/MetaHumans")
task.set_editor_property("destination_name", "SKM_test_UEFN78_CopyW")
task.set_editor_property("automated", True)
task.set_editor_property("save", True)
task.set_editor_property("options", options)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
print("IMPORT_OK")
'''

AUDIT_CODE = r'''
import math, os, unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for a in subsystem.get_all_level_actors():
    if a.get_actor_label().startswith("CopyW_Audit"):
        subsystem.destroy_actor(a)
mesh = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFN78_CopyW")
actor = subsystem.spawn_actor_from_class(unreal.SkeletalMeshActor, unreal.Vector(0,0,0), unreal.Rotator())
actor.set_actor_label("CopyW_Audit")
actor.skeletal_mesh_component.set_skeletal_mesh_asset(mesh)
anim = unreal.load_asset("/Game/Characters/UEFN_Mannequin/Animations/Traversal/Catch/Cliff/M_Neutral_Traversal_Catch_Cliff_high_stand")
comp = actor.skeletal_mesh_component
comp.set_update_animation_in_editor(True)
comp.set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
comp.override_animation_data(anim, False, False, 0.8, 0.0)
comp.set_position(0.8, False)
hand = comp.get_socket_location("hand_r")
lower = comp.get_socket_location("lowerarm_r")
axis = unreal.Vector(hand.x-lower.x, hand.y-lower.y, hand.z-lower.z)
slen = math.sqrt(axis.x**2+axis.y**2+axis.z**2) or 1
side = unreal.Vector(-axis.y/slen*55, axis.x/slen*55, 18)
cam = unreal.Vector(hand.x+side.x, hand.y+side.y, hand.z+side.z)
rot = unreal.MathLibrary.find_look_at_rotation(cam, hand)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(cam, rot)
path = os.path.join(unreal.Paths.project_saved_dir(), "CodexLiveShots", "CopyW_CliffCatch_hand_r.png")
unreal.AutomationLibrary.finish_loading_before_screenshot()
unreal.AutomationLibrary.take_high_res_screenshot(1800, 1400, path)
print("SHOT|" + path)
subsystem.destroy_actor(actor)
'''

def run(remote, code):
    r = remote.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
    out = "".join(e.get("output", "") for e in r.get("output", []))
    if not r.get("success"):
        raise RuntimeError(out)
    return out

remote = remote_execution.RemoteExecution()
remote.start()
try:
    deadline = time.monotonic() + 15
    while not remote.remote_nodes and time.monotonic() < deadline:
        time.sleep(0.25)
    remote.open_command_connection(remote.remote_nodes[0]["node_id"])
    print(run(remote, IMPORT_CODE).strip())
    time.sleep(2)
    print(run(remote, AUDIT_CODE).strip())
finally:
    remote.stop()
