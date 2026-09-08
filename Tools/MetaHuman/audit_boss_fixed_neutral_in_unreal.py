"""Capture the corrected Boss reference surface and material assignment in UE."""

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path


REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)
import remote_execution


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
OUT_DIR = PROJECT / "Saved" / "CodexLiveShots" / "BossUEFNFixed"
AUDIT = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_UEFN_FixedNeutralUnrealAudit.json"
)

SETUP = r'''
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in subsystem.get_all_level_actors():
    if actor.get_actor_label() == "BossUEFN_FixedNeutralAudit":
        subsystem.destroy_actor(actor)
mesh = unreal.load_asset("/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN")
if not isinstance(mesh, unreal.SkeletalMesh):
    raise RuntimeError("Missing corrected Boss mesh")
actor = subsystem.spawn_actor_from_class(
    unreal.SkeletalMeshActor,
    unreal.Vector(0.0, 0.0, -5000.0),
    unreal.Rotator(),
)
actor.set_actor_label("BossUEFN_FixedNeutralAudit")
component = actor.skeletal_mesh_component
component.set_skeletal_mesh_asset(mesh)
component.set_update_animation_in_editor(True)
component.set_editor_property("forced_lod_model", 1)
component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem
).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "r.MotionBlurQuality 0")
unreal.SystemLibrary.execute_console_command(world, "r.ScreenPercentage 100")
unreal.SystemLibrary.execute_console_command(world, "ShowFlag.Grid 0")
print("BOSS_FIXED_NEUTRAL_SETUP")
'''

CAPTURE = r'''
import os
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = next(
    actor for actor in subsystem.get_all_level_actors()
    if actor.get_actor_label() == "BossUEFN_FixedNeutralAudit"
)
component = actor.skeletal_mesh_component
target = __TARGET__
head = component.get_socket_location("head")
pelvis = component.get_socket_location("pelvis")
if target == "Full":
    center = unreal.Vector(
        (head.x + pelvis.x) * 0.5,
        (head.y + pelvis.y) * 0.5,
        (head.z + pelvis.z) * 0.5,
    )
    camera = unreal.Vector(center.x, center.y + 315.0, center.z + 8.0)
elif target in ("Neck", "BackNeck"):
    chest = component.get_socket_location("spine_05")
    center = unreal.Vector(
        (head.x + chest.x) * 0.5,
        (head.y + chest.y) * 0.5,
        (head.z + chest.z) * 0.5,
    )
    direction = 1.0 if target == "Neck" else -1.0
    camera = unreal.Vector(
        center.x, center.y + direction * 115.0, center.z + 2.0
    )
else:
    raise RuntimeError("Unknown target " + target)
rotation = unreal.MathLibrary.find_look_at_rotation(camera, center)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera, rotation)
path = __CAPTURE_OUTPUT__
os.makedirs(os.path.dirname(path), exist_ok=True)
unreal.AutomationLibrary.finish_loading_before_screenshot()
# The automation helper can silently lose editor-viewport captures when
# several are queued close together.  HighResShot is the documented viewport
# command and accepts an explicit filename and resolution.
command = 'HighResShot filename="' + path.replace("\\", "/") + '" 1600x1200'
unreal.SystemLibrary.execute_console_command(world, command)
print("BOSS_FIXED_NEUTRAL_SHOT|" + path)
'''

CLEANUP = r'''
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in subsystem.get_all_level_actors():
    if actor.get_actor_label() == "BossUEFN_FixedNeutralAudit":
        subsystem.destroy_actor(actor)
print("BOSS_FIXED_NEUTRAL_CLEANUP")
'''


def run(remote, code):
    result = remote.run_command(
        code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE
    )
    output = "".join(
        entry.get("output", "") for entry in result.get("output", [])
    )
    if not result.get("success"):
        raise RuntimeError(result.get("result", "Remote execution failed") + output)
    return output


def connect():
    remote = remote_execution.RemoteExecution()
    remote.start()
    deadline = time.monotonic() + 20.0
    while not remote.remote_nodes and time.monotonic() < deadline:
        time.sleep(0.2)
    if not remote.remote_nodes:
        remote.stop()
        raise RuntimeError("No running Unreal remote node")
    remote.open_command_connection(remote.remote_nodes[0]["node_id"])
    return remote


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    remote = connect()
    images = {}
    try:
        print(run(remote, SETUP).strip())
        time.sleep(3.0)
        for target in ("Full", "Neck", "BackNeck"):
            output = OUT_DIR / f"Unreal_Boss_FixedNeutral_{target}.png"
            capture_output = (
                Path(tempfile.gettempdir())
                / f"Codex_BossSkin_{target}.png"
            )
            # High-res screenshots are asynchronous.  Delete an older capture
            # first so the wait below cannot accidentally accept stale pixels
            # from the previous mesh revision.
            if output.exists():
                output.unlink()
            if capture_output.exists():
                capture_output.unlink()
            code = CAPTURE.replace("__TARGET__", repr(target)).replace(
                "__CAPTURE_OUTPUT__", repr(str(capture_output))
            )
            print(run(remote, code).strip())
            deadline = time.monotonic() + 30.0
            while (
                not capture_output.is_file()
                and time.monotonic() < deadline
            ):
                time.sleep(0.25)
            if not capture_output.is_file():
                raise RuntimeError(
                    "Missing Unreal screenshot: " + str(capture_output)
                )
            shutil.copy2(capture_output, output)
            capture_output.unlink()
            images[target] = str(output)
            # HighResShot accepts a single request per rendered frame.
            time.sleep(1.0)
    finally:
        try:
            print(run(remote, CLEANUP).strip())
        except Exception as error:
            print("Boss neutral cleanup failed: " + str(error))
        remote.stop()
    report = {"images": images}
    AUDIT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("BOSS_FIXED_NEUTRAL_AUDIT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
