"""Capture the Boss seam with Body/Face forced to one neutral material."""

import os
import sys
import time
from pathlib import Path


REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)
import remote_execution


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
OUTPUT = (
    PROJECT
    / "Saved/CodexLiveShots/BossUEFNFixed/"
    / "Unreal_Boss_BackNeck_OneNeutralMaterial.png"
)

CODE = r'''
import os
import unreal
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in actors.get_all_level_actors():
    if actor.get_actor_label() == "BossUEFN_SeamNeutralMaterial":
        actors.destroy_actor(actor)
mesh = unreal.load_asset("/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN")
material = unreal.load_asset("/Engine/BasicShapes/BasicShapeMaterial")
actor = actors.spawn_actor_from_class(
    unreal.SkeletalMeshActor, unreal.Vector(0, 0, -5000), unreal.Rotator()
)
actor.set_actor_label("BossUEFN_SeamNeutralMaterial")
component = actor.skeletal_mesh_component
component.set_skeletal_mesh_asset(mesh)
component.set_update_animation_in_editor(True)
component.set_editor_property("forced_lod_model", 1)
component.set_material(0, material)
component.set_material(7, material)
head = component.get_socket_location("head")
chest = component.get_socket_location("spine_05")
center = unreal.Vector(
    (head.x + chest.x) * 0.5,
    (head.y + chest.y) * 0.5,
    (head.z + chest.z) * 0.5,
)
camera = unreal.Vector(center.x, center.y - 115.0, center.z + 2.0)
rotation = unreal.MathLibrary.find_look_at_rotation(camera, center)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera, rotation)
path = __OUTPUT__
os.makedirs(os.path.dirname(path), exist_ok=True)
unreal.AutomationLibrary.finish_loading_before_screenshot()
unreal.AutomationLibrary.take_high_res_screenshot(1600, 1200, path)
print("BOSS_NEUTRAL_MATERIAL_SHOT|" + path)
'''

CLEANUP = r'''
import unreal
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in actors.get_all_level_actors():
    if actor.get_actor_label() == "BossUEFN_SeamNeutralMaterial":
        actors.destroy_actor(actor)
'''


def run(remote, code):
    result = remote.run_command(
        code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE
    )
    if not result.get("success"):
        raise RuntimeError(result.get("result", "Remote execution failed"))


def main():
    if OUTPUT.exists():
        OUTPUT.unlink()
    remote = remote_execution.RemoteExecution()
    remote.start()
    try:
        deadline = time.monotonic() + 20
        while not remote.remote_nodes and time.monotonic() < deadline:
            time.sleep(0.2)
        if not remote.remote_nodes:
            raise RuntimeError("No Unreal remote node")
        remote.open_command_connection(remote.remote_nodes[0]["node_id"])
        run(remote, CODE.replace("__OUTPUT__", repr(str(OUTPUT))))
        deadline = time.monotonic() + 12
        while not OUTPUT.is_file() and time.monotonic() < deadline:
            time.sleep(0.25)
        if not OUTPUT.is_file():
            raise RuntimeError("Neutral material screenshot missing")
    finally:
        try:
            run(remote, CLEANUP)
        finally:
            remote.stop()
    print(str(OUTPUT))


if __name__ == "__main__":
    main()
