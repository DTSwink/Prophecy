import os
import sys
import time


REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)

import remote_execution


POSES = (
    (
        "WristBlendDemandingClimb",
        "/Game/Characters/UEFN_Mannequin/Animations/Traversal/Climb/M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot",
        2.0,
    ),
)


SETUP_CODE = r'''
import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
uefn_actor = next(actor for actor in actors if actor.get_actor_label() == "UEFN_Far_Audit")
meta_actor = next(actor for actor in actors if actor.get_actor_label() == "MetaHuman_Far_Audit")
uefn_component = uefn_actor.skeletal_mesh_component
body = next(component for component in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if component.get_name() == "Body")
face = next(component for component in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if component.get_name() == "Face")
test_body = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody_WristBlendTest")
body.set_skeletal_mesh_asset(test_body)
if body.skeletal_mesh.get_path_name() != "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody_WristBlendTest.SKM_test_UEFNDirectBody_WristBlendTest":
    raise RuntimeError("MetaHuman audit actor is not using the final direct body")
if face.get_attach_parent() != body:
    raise RuntimeError("MetaHuman face is not attached to Body")

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "r.MotionBlurQuality 0")
unreal.SystemLibrary.execute_console_command(world, "r.DefaultFeature.MotionBlur 0")
unreal.SystemLibrary.execute_console_command(world, "r.ScreenPercentage 100")
unreal.EditorLevelLibrary.set_level_viewport_camera_info(
    unreal.Vector(220.0, 0.0, 108.0),
    unreal.Rotator(pitch=0.0, yaw=180.0, roll=0.0),
)
print("FINAL_WIDE_SETUP|camera=(220,0,108)|face_parent=Body|body=" + body.skeletal_mesh.get_name())
'''


POSE_CODE = r'''
import unreal

animation_path = __ANIMATION_PATH__
sample_time = __SAMPLE_TIME__
lod_mode = __LOD_MODE__
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
uefn_actor = next(actor for actor in actors if actor.get_actor_label() == "UEFN_Far_Audit")
meta_actor = next(actor for actor in actors if actor.get_actor_label() == "MetaHuman_Far_Audit")
uefn_component = uefn_actor.skeletal_mesh_component
body = next(component for component in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if component.get_name() == "Body")
lod_sync = next(component for component in meta_actor.get_components_by_class(unreal.ActorComponent) if component.get_name() == "LODSync")
animation = unreal.load_asset(animation_path)
if not animation:
    raise RuntimeError("Missing animation: " + animation_path)

for component in (uefn_component, body):
    component.override_animation_data(animation, False, False, sample_time, 0.0)
    component.set_update_animation_in_editor(True)

if lod_mode == "LOD0":
    uefn_component.set_editor_property("forced_lod_model", 1)
    lod_sync.set_editor_property("forced_lod", 0)
else:
    uefn_component.set_editor_property("forced_lod_model", 0)
    lod_sync.set_editor_property("forced_lod", -1)

print("FINAL_WIDE_POSE_SET|{}|{}|time={}".format(animation.get_name(), lod_mode, sample_time))
'''


VERIFY_CAPTURE_CODE = r'''
import json
import math
import os
import unreal

pose_name = __POSE_NAME__
lod_mode = __LOD_MODE__
filename = __FILENAME__
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
uefn_actor = next(actor for actor in actors if actor.get_actor_label() == "UEFN_Far_Audit")
meta_actor = next(actor for actor in actors if actor.get_actor_label() == "MetaHuman_Far_Audit")
uefn_component = uefn_actor.skeletal_mesh_component
body = next(component for component in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if component.get_name() == "Body")
face = next(component for component in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if component.get_name() == "Face")
lod_sync = next(component for component in meta_actor.get_components_by_class(unreal.ActorComponent) if component.get_name() == "LODSync")

snapshot_path = os.path.join(unreal.Paths.project_dir(), "Tools", "MetaHuman", "skeleton_snapshots.json")
with open(snapshot_path, "r", encoding="utf-8") as handle:
    snapshot = json.load(handle)
excluded = set(snapshot["fit_recipe"]["uefn_only_bones"])
bone_names = [entry["name"] for entry in snapshot["uefn_reference"]["bones"] if entry["name"] not in excluded]

max_translation_delta = 0.0
max_rotation_delta_degrees = 0.0
max_scale_delta = 0.0
worst_translation_bone = None
worst_rotation_bone = None
for bone_name in bone_names:
    source = uefn_component.get_socket_transform(bone_name, unreal.RelativeTransformSpace.RTS_COMPONENT)
    target = body.get_socket_transform(bone_name, unreal.RelativeTransformSpace.RTS_COMPONENT)
    delta = source.translation - target.translation
    translation_delta = math.sqrt(delta.x * delta.x + delta.y * delta.y + delta.z * delta.z)
    if translation_delta > max_translation_delta:
        max_translation_delta = translation_delta
        worst_translation_bone = bone_name
    source_q = source.rotation
    target_q = target.rotation
    dot = abs(source_q.x * target_q.x + source_q.y * target_q.y + source_q.z * target_q.z + source_q.w * target_q.w)
    rotation_delta = math.degrees(2.0 * math.acos(max(-1.0, min(1.0, dot))))
    if rotation_delta > max_rotation_delta_degrees:
        max_rotation_delta_degrees = rotation_delta
        worst_rotation_bone = bone_name
    scale_delta = max(
        abs(source.scale3d.x - target.scale3d.x),
        abs(source.scale3d.y - target.scale3d.y),
        abs(source.scale3d.z - target.scale3d.z),
    )
    max_scale_delta = max(max_scale_delta, scale_delta)

body_head = body.get_socket_transform("head", unreal.RelativeTransformSpace.RTS_WORLD).translation
face_head = face.get_socket_transform("head", unreal.RelativeTransformSpace.RTS_WORLD).translation
head_delta_vector = body_head - face_head
head_delta = math.sqrt(
    head_delta_vector.x * head_delta_vector.x
    + head_delta_vector.y * head_delta_vector.y
    + head_delta_vector.z * head_delta_vector.z
)

if max_translation_delta > 0.1 or max_rotation_delta_degrees > 0.01 or max_scale_delta > 0.2:
    raise RuntimeError(
        "Pose mismatch: translation={} bone={}, rotation={} bone={}, scale={}".format(
            max_translation_delta,
            worst_translation_bone,
            max_rotation_delta_degrees,
            worst_rotation_bone,
            max_scale_delta,
        )
    )
if head_delta > 0.01:
    raise RuntimeError("Face/head mismatch: {} cm".format(head_delta))

path = os.path.join(unreal.Paths.project_saved_dir(), "CodexLiveShots", filename)
os.makedirs(os.path.dirname(path), exist_ok=True)
unreal.AutomationLibrary.finish_loading_before_screenshot()
try:
    unreal.AutomationLibrary.take_high_res_screenshot(2200, 1375, path)
except TypeError:
    unreal.AutomationLibrary.take_high_res_screenshot(
        2200, 1375, path, None, False, False,
        unreal.ComparisonTolerance.LOW, filename, 0.1, True,
    )
print(
    "FINAL_WIDE_VERIFY|{}|{}|bones={}|max_t_cm={:.8f}|max_r_deg={:.8f}|max_s={:.8f}|face_head_cm={:.8f}|uefn_forced={}|body_forced={}|face_forced={}|lodsync={}|screenshot={}".format(
        pose_name,
        lod_mode,
        len(bone_names),
        max_translation_delta,
        max_rotation_delta_degrees,
        max_scale_delta,
        head_delta,
        uefn_component.forced_lod_model,
        body.forced_lod_model,
        face.forced_lod_model,
        lod_sync.get_editor_property("forced_lod"),
        path,
    )
)
'''


def run(remote, code):
    result = remote.run_command(
        code,
        unattended=True,
        exec_mode=remote_execution.MODE_EXEC_FILE,
    )
    for entry in result.get("output", []):
        print(entry.get("output", ""))
    if not result.get("success"):
        raise RuntimeError(result.get("result", "Remote execution failed"))


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
    time.sleep(2.0)
    for pose_name, animation_path, sample_time in POSES:
        for lod_mode in ("LOD0", "Auto"):
            pose_code = (
                POSE_CODE.replace("__ANIMATION_PATH__", repr(animation_path))
                .replace("__SAMPLE_TIME__", repr(sample_time))
                .replace("__LOD_MODE__", repr(lod_mode))
            )
            run(remote, pose_code)
            time.sleep(2.0)
            filename = "MetaHuman_FinalWide_{}_{}.png".format(pose_name, lod_mode)
            capture_code = (
                VERIFY_CAPTURE_CODE.replace("__POSE_NAME__", repr(pose_name))
                .replace("__LOD_MODE__", repr(lod_mode))
                .replace("__FILENAME__", repr(filename))
            )
            run(remote, capture_code)
            time.sleep(3.0)
finally:
    remote.stop()

print("FINAL_WIDE_AUDIT_COMPLETE")
