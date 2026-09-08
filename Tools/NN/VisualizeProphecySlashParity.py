"""Run inside the editor: source and actual NNE output, paused at the same frame.

Creates only transient comparison actors in the current flat map; never saves
the level or changes production agents, their materials, or camera controls.
"""
import json
import math
from pathlib import Path
import sys
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
contract = json.loads((root / "Content/locomotion/NN/prophecy_slash_runtime.json").read_text())
reference = json.loads((Path(contract["reference_directory"]) / "rollout_unreal.json").read_text())
actual = json.loads((root / "Saved/SlashParity/unreal_nne_rollout.json").read_text())
frame = int(sys.argv[1]) if len(sys.argv) > 1 else 14
mesh = unreal.load_asset("/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin")
for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    if actor.get_actor_label().startswith("SlashVisual"):
        unreal.EditorLevelLibrary.destroy_actor(actor)


def local_position(position):
    delta = [position[i] - contract["root_position_m"][i] for i in range(3)]
    local = [sum(delta[j] * contract["root_rotation"][i][j] for j in range(3)) for i in range(3)]
    return unreal.Vector(local[0] * 100, -local[1] * 100, local[2] * 100)


def local_rotation(rotation):
    local = [[sum(rotation[i][k] * contract["root_rotation"][j][k] for k in range(3)) for j in range(3)] for i in range(3)]
    signs = [1, -1, 1]
    axes = [unreal.Vector(*(local[i][j] * signs[i] * signs[j] for j in range(3))) for i in range(3)]
    return unreal.MathLibrary.make_rotation_from_axes(*axes)


errors = []
for column, (label, data) in enumerate((("Source", reference), ("UnrealNNE", actual))):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.Actor, unreal.Vector(column * 240, 0, 0))
    actor.set_actor_label(f"SlashVisual_{label}_Frame{frame}")
    component = actor.call_method("AddComponentByClass", args=(unreal.PoseableMeshComponent.static_class(), False, unreal.Transform(), False))
    component.set_skeletal_mesh(mesh)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    pose = data["frames"][frame]
    for name, position, rotation in zip(contract["bone_names"], pose["globalJointPositionsM"], pose["globalJointRotations3x3"]):
        component.set_bone_transform_by_name(unreal.Name(name), unreal.Transform(location=local_position(position), rotation=local_rotation(rotation)), unreal.BoneSpaces.COMPONENT_SPACE)
    for name, position in zip(contract["bone_names"], pose["globalJointPositionsM"]):
        got = component.get_bone_location_by_name(unreal.Name(name), unreal.BoneSpaces.COMPONENT_SPACE)
        expected = local_position(position)
        errors.append(math.sqrt((got.x - expected.x)**2 + (got.y - expected.y)**2 + (got.z - expected.z)**2))

camera = unreal.Vector(280, 390, 205)
look = unreal.Vector(120, 0, 110)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera, unreal.MathLibrary.find_look_at_rotation(camera, look))
output = root / f"Saved/SlashParity/visual_frame_{frame}.png"
world = unreal.EditorLevelLibrary.get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "Prophecy.RefreshSlashVisuals")
unreal.EditorLevelLibrary.clear_actor_selection_set()
unreal.SystemLibrary.execute_console_command(world, "ShowFlag.BillboardSprites 0")
unreal.SystemLibrary.execute_console_command(world, "ShowFlag.ModeWidgets 0")
unreal.SystemLibrary.execute_console_command(world, f'HighResShot filename="{output.as_posix()}" 1280x720')
print(json.dumps({"frame": frame, "maximum_rendered_joint_error_cm": max(errors), "screenshot": str(output)}))
