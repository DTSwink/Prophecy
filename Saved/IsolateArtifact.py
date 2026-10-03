import sys
import time

REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)

import remote_execution

CODE_TEMPLATE = r'''
import math
import os
import unreal

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
reduced = next(a for a in actors if a.get_actor_label() == "Reduced78_Audit")
face_actor = next(a for a in actors if a.get_actor_label() == "Reduced78_Audit_Face")
mann = next(a for a in actors if a.get_actor_label() == "UEFN_Ref_Audit")

reduced.skeletal_mesh_component.set_visibility(__SHOW_BODY__)
face_actor.skeletal_mesh_component.set_visibility(__SHOW_FACE__)
mann.skeletal_mesh_component.set_visibility(__SHOW_MANN__)

animation = unreal.load_asset("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop")
for actor in (reduced, mann):
    component = actor.skeletal_mesh_component
    component.set_update_animation_in_editor(True)
    component.override_animation_data(animation, False, False, 1.0, 0.0)
    component.set_position(1.0, False)

component = reduced.skeletal_mesh_component
head = component.get_socket_location("head")
pelvis = component.get_socket_location("pelvis")
print("SOCKETS|head=({:.1f},{:.1f},{:.1f})|pelvis=({:.1f},{:.1f},{:.1f})".format(
    head.x, head.y, head.z, pelvis.x, pelvis.y, pelvis.z))
bounds_origin, bounds_ext = reduced.get_actor_bounds(False)
print("BODY_BOUNDS|origin=({:.1f},{:.1f},{:.1f})|ext=({:.1f},{:.1f},{:.1f})".format(
    bounds_origin.x, bounds_origin.y, bounds_origin.z, bounds_ext.x, bounds_ext.y, bounds_ext.z))
fb_origin, fb_ext = face_actor.get_actor_bounds(False)
print("FACE_BOUNDS|origin=({:.1f},{:.1f},{:.1f})|ext=({:.1f},{:.1f},{:.1f})".format(
    fb_origin.x, fb_origin.y, fb_origin.z, fb_ext.x, fb_ext.y, fb_ext.z))

center = unreal.Vector((head.x + pelvis.x) / 2, (head.y + pelvis.y) / 2, (head.z + pelvis.z) / 2)
camera_pos = unreal.Vector(center.x + 260.0, center.y - 180.0, center.z + 40.0)
rotation = unreal.MathLibrary.find_look_at_rotation(camera_pos, center)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_pos, rotation)
path = os.path.join(unreal.Paths.project_saved_dir(), "CodexLiveShots", __FILENAME__)
unreal.AutomationLibrary.finish_loading_before_screenshot()
try:
    unreal.AutomationLibrary.take_high_res_screenshot(1600, 1200, path)
except TypeError:
    unreal.AutomationLibrary.take_high_res_screenshot(
        1600, 1200, path, None, False, False,
        unreal.ComparisonTolerance.LOW, __FILENAME__, 0.1, True,
    )
print("ISOLATE_SHOT|" + path)
'''


def run(remote, code):
    result = remote.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
    output = "".join(entry.get("output", "") for entry in result.get("output", []))
    if not result.get("success"):
        raise RuntimeError(result.get("result", "failed") + "\n" + output)
    return output


def main():
    remote = remote_execution.RemoteExecution()
    remote.start()
    try:
        deadline = time.monotonic() + 15.0
        while not remote.remote_nodes and time.monotonic() < deadline:
            time.sleep(0.25)
        remote.open_command_connection(remote.remote_nodes[0]["node_id"])
        cases = [
            ("BodyOnly", "True", "False", "False"),
            ("FaceOnly", "False", "True", "False"),
            ("MannOnly", "False", "False", "True"),
        ]
        for name, show_body, show_face, show_mann in cases:
            code = (
                CODE_TEMPLATE
                .replace("__SHOW_BODY__", show_body)
                .replace("__SHOW_FACE__", show_face)
                .replace("__SHOW_MANN__", show_mann)
                .replace("__FILENAME__", repr("Isolate_{}.png".format(name)))
            )
            output = run(remote, code)
            for line in output.splitlines():
                if line.startswith(("SOCKETS", "BODY_BOUNDS", "FACE_BOUNDS", "ISOLATE_SHOT")):
                    print("{} {}".format(name, line))
            time.sleep(3.0)
    finally:
        remote.stop()
    print("ISOLATE_DONE")


if __name__ == "__main__":
    main()
