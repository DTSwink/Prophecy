"""Relax bind-conversion folds at wrists/ankles without touching distant anatomy."""

import os

import bpy


PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
SOURCE = os.environ.get("PROPHECY_MH_REPAIR_SOURCE", "Body_UEFN78_DQ.blend")
TAG = os.environ.get("PROPHECY_MH_REPAIR_TAG", "_Repair")
FACTOR = float(os.environ.get("PROPHECY_MH_REPAIR_FACTOR", "0.16"))
ITERATIONS = int(os.environ.get("PROPHECY_MH_REPAIR_ITERATIONS", "16"))

JOINTS = (
    ("wrist_r", "hand_r", 3.0, 7.0),
    ("wrist_l", "hand_l", 3.0, 7.0),
    ("ankle_r", "foot_r", 4.0, 9.0),
    ("ankle_l", "foot_l", 4.0, 9.0),
)


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def main():
    source_path = os.path.join(EXCHANGE, SOURCE)
    output_blend = os.path.join(EXCHANGE, "Body_UEFN78{}.blend".format(TAG))
    bpy.ops.wm.open_mainfile(filepath=source_path)
    mesh = max(
        (obj for obj in bpy.data.objects if obj.type == "MESH"),
        key=lambda obj: len(obj.data.vertices),
    )
    armature = next(mod.object for mod in mesh.modifiers if mod.type == "ARMATURE")
    armature.data.pose_position = "REST"
    bpy.context.view_layer.update()

    for label, bone_name, inner_radius, outer_radius in JOINTS:
        joint = armature.data.bones[bone_name].head_local
        group_name = "_repair_" + label
        old = mesh.vertex_groups.get(group_name)
        if old is not None:
            mesh.vertex_groups.remove(old)
        group = mesh.vertex_groups.new(name=group_name)
        selected = 0
        for vertex in mesh.data.vertices:
            distance = (vertex.co - joint).length
            if distance >= outer_radius:
                continue
            if distance <= inner_radius:
                weight = 1.0
            else:
                weight = 1.0 - smoothstep(
                    (distance - inner_radius) / (outer_radius - inner_radius)
                )
            group.add([vertex.index], weight, "REPLACE")
            selected += 1

        modifier = mesh.modifiers.new(name="Repair_" + label, type="LAPLACIANSMOOTH")
        modifier.vertex_group = group_name
        modifier.lambda_factor = FACTOR
        modifier.lambda_border = FACTOR
        modifier.iterations = ITERATIONS
        modifier.use_volume_preserve = True
        bpy.context.view_layer.objects.active = mesh
        while mesh.modifiers.find(modifier.name) > 0:
            bpy.ops.object.modifier_move_up(modifier=modifier.name)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        applied_group = mesh.vertex_groups.get(group_name)
        if applied_group is not None:
            mesh.vertex_groups.remove(applied_group)
        print("REPAIRED|{}|verts={}|factor={}|iterations={}".format(
            label, selected, FACTOR, ITERATIONS))

    bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    print("REST_REPAIR_DONE|{}".format(output_blend))


main()
