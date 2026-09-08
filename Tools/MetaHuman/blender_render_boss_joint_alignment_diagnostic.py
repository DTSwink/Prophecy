"""Render an unambiguous mesh-to-joint alignment diagnostic.

This deliberately does not draw Blender/FBX bone tails.  Every sphere is an
actual UEFN joint head, and every colored line joins one joint head to its
child joint head.  Green spheres are inside the mesh; red spheres are outside.
"""

from __future__ import annotations

import json
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
BLEND = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_UEFN_ExportClean.blend"
)
OUT_DIR = (
    PROJECT
    / "Saved"
    / "BlenderShots"
    / "BossUEFNJointAlignmentDiagnostic"
)
REPORT = OUT_DIR / "Boss_UEFN_JointAlignment.json"

FINGER_COLORS = {
    "hand": (0.15, 0.65, 1.0, 1.0),
    "thumb": (1.0, 0.35, 0.08, 1.0),
    "index": (1.0, 0.82, 0.05, 1.0),
    "middle": (0.15, 0.95, 0.25, 1.0),
    "ring": (0.05, 0.85, 1.0, 1.0),
    "pinky": (0.75, 0.28, 1.0, 1.0),
}


def emission_material(name, color):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = 2.0
    material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def transparent_mesh_material():
    material = bpy.data.materials.new("Diagnostic transparent mesh")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.inputs["Base Color"].default_value = (0.22, 0.30, 0.38, 1.0)
    principled.inputs["Roughness"].default_value = 0.8
    mix = nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.23
    material.node_tree.links.new(transparent.outputs[0], mix.inputs[1])
    material.node_tree.links.new(principled.outputs[0], mix.inputs[2])
    material.node_tree.links.new(mix.outputs[0], output.inputs["Surface"])
    try:
        material.surface_render_method = "DITHERED"
    except AttributeError:
        material.blend_method = "BLEND"
    material.use_transparency_overlap = False
    return material


def add_sphere(name, position, radius, material):
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=3,
        radius=radius,
        location=position,
    )
    sphere = bpy.context.object
    sphere.name = name
    sphere.data.materials.append(material)
    sphere.visible_shadow = False
    return sphere


def add_cylinder(name, start, end, radius, material):
    direction = end - start
    if direction.length < 1.0e-8:
        return None
    midpoint = (start + end) * 0.5
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12,
        radius=radius,
        depth=direction.length,
        location=midpoint,
    )
    cylinder = bpy.context.object
    cylinder.name = name
    cylinder.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    cylinder.data.materials.append(material)
    cylinder.visible_shadow = False
    return cylinder


def add_label(name, text, position, material):
    curve = bpy.data.curves.new(name + "_Geometry", "FONT")
    curve.body = text
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = 0.008
    curve.extrude = 0.00015
    label = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(label)
    label.location = position
    label.data.materials.append(material)
    label.visible_shadow = False
    return label


def finger_family(name):
    if name.startswith("hand_"):
        return "hand"
    for family in ("thumb", "index", "middle", "ring", "pinky"):
        if name.startswith(family + "_"):
            return family
    raise RuntimeError("Unexpected hand bone: " + name)


def short_label(name):
    side = name.rsplit("_", 1)[-1].upper()
    if name.startswith("hand_"):
        return "HAND-" + side
    family = finger_family(name)
    code = {
        "thumb": "T",
        "index": "I",
        "middle": "M",
        "ring": "R",
        "pinky": "P",
    }[family]
    if "metacarpal" in name:
        joint = "0"
    else:
        pieces = name.split("_")
        joint = next((piece for piece in pieces if piece.isdigit()), "?")
    return code + joint + "-" + side


def mesh_bvh_world(mesh):
    vertices = [mesh.matrix_world @ vertex.co for vertex in mesh.data.vertices]
    polygons = [list(polygon.vertices) for polygon in mesh.data.polygons]
    return BVHTree.FromPolygons(vertices, polygons, all_triangles=False)


def ray_intersection_count(bvh, point, direction):
    origin = point.copy()
    remaining = 10.0
    count = 0
    for _iteration in range(256):
        hit, _normal, _index, distance = bvh.ray_cast(
            origin, direction, remaining
        )
        if hit is None:
            break
        count += 1
        step = max(distance + 1.0e-5, 1.0e-5)
        origin += direction * step
        remaining -= step
        if remaining <= 0.0:
            break
    return count


def point_inside_mesh(bvh, point):
    directions = (
        Vector((1.0, 0.173, 0.319)).normalized(),
        Vector((-0.231, 1.0, 0.417)).normalized(),
        Vector((0.293, -0.371, 1.0)).normalized(),
    )
    votes = [
        ray_intersection_count(bvh, point, direction) % 2 == 1
        for direction in directions
    ]
    return sum(votes) >= 2, votes


def look_at(camera, target):
    camera.rotation_euler = (
        target - camera.location
    ).to_track_quat("-Z", "Y").to_euler()


def orient_labels(labels, camera):
    rotation = camera.rotation_euler.copy()
    for label in labels:
        label.rotation_euler = rotation


def render_view(
    scene,
    camera,
    labels,
    target,
    view_direction,
    ortho_scale,
    path,
):
    camera.data.ortho_scale = ortho_scale
    camera.location = target + view_direction.normalized() * 1.5
    look_at(camera, target)
    orient_labels(labels, camera)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.008, 0.008, 0.012)

    rig = bpy.data.objects["root"]
    mesh = bpy.data.objects["SKM_Boss_UEFN"]
    rig.hide_render = True

    # Render the surface translucent and add an explicit triangulated wire
    # overlay, so a marker cannot be mistaken for a bone tail or hidden joint.
    mesh.data.materials.clear()
    mesh.data.materials.append(transparent_mesh_material())
    for polygon in mesh.data.polygons:
        polygon.material_index = 0
    mesh.visible_shadow = False

    wire = mesh.copy()
    wire.data = mesh.data.copy()
    wire.name = "Diagnostic mesh wire"
    scene.collection.objects.link(wire)
    wire.data.materials.clear()
    wire.data.materials.append(
        emission_material("Diagnostic wire", (0.20, 0.46, 0.62, 1.0))
    )
    wireframe = wire.modifiers.new("Diagnostic wireframe", "WIREFRAME")
    wireframe.thickness = 0.00022
    wireframe.use_replace = True
    wire.visible_shadow = False

    head_inside = emission_material("Joint head inside", (0.05, 1.0, 0.15, 1.0))
    head_outside = emission_material("Joint head outside", (1.0, 0.02, 0.02, 1.0))
    label_material = emission_material("Joint labels", (1.0, 1.0, 1.0, 1.0))
    family_materials = {
        family: emission_material("Chain " + family, color)
        for family, color in FINGER_COLORS.items()
    }

    hand_bones = [
        bone
        for bone in rig.data.bones
        if bone.name.startswith(
            ("hand_", "thumb_", "index_", "middle_", "ring_", "pinky_")
        )
    ]
    selected_names = {bone.name for bone in hand_bones}
    bvh = mesh_bvh_world(mesh)
    labels = []
    report = {}
    head_world = {}

    for bone in hand_bones:
        position = rig.matrix_world @ bone.head_local
        head_world[bone.name] = position
        inside, votes = point_inside_mesh(bvh, position)
        nearest = bvh.find_nearest(position)
        nearest_distance_mm = nearest[3] * 1000.0 if nearest else None
        report[bone.name] = {
            "head_world_m": list(position),
            "inside_mesh": inside,
            "inside_ray_votes": votes,
            "nearest_surface_distance_mm": nearest_distance_mm,
            "parent": bone.parent.name if bone.parent else None,
        }
        add_sphere(
            "HEAD_" + bone.name,
            position,
            0.0032,
            head_inside if inside else head_outside,
        )
        label_offset = Vector((0.0, 0.0, 0.0075))
        labels.append(
            add_label(
                "LABEL_" + bone.name,
                short_label(bone.name),
                position + label_offset,
                label_material,
            )
        )

    # Draw only anatomical head-to-head relationships. FBX tail locations are
    # intentionally ignored because they encode orientation in Blender and are
    # not additional Unreal joints.
    for bone in hand_bones:
        if bone.parent and bone.parent.name in selected_names:
            add_cylinder(
                "JOINT_LINK_" + bone.name,
                head_world[bone.parent.name],
                head_world[bone.name],
                0.00115,
                family_materials[finger_family(bone.name)],
            )

    camera_data = bpy.data.cameras.new("Joint diagnostic camera")
    camera_data.type = "ORTHO"
    camera = bpy.data.objects.new("Joint diagnostic camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    views = {
        "Front": Vector((0.0, -1.0, 0.0)),
        "Back": Vector((0.0, 1.0, 0.0)),
        "LeftSide": Vector((-1.0, 0.0, 0.0)),
        "RightSide": Vector((1.0, 0.0, 0.0)),
    }
    for side, hand_name in (("Left", "hand_l"), ("Right", "hand_r")):
        side_points = [
            position
            for name, position in head_world.items()
            if name.endswith("_" + side[0].lower())
        ]
        target = sum(side_points, Vector()) / len(side_points)
        for view_name, direction in views.items():
            render_view(
                scene,
                camera,
                labels,
                target,
                direction,
                0.31,
                OUT_DIR / f"Boss_{side}Hand_{view_name}.png",
            )

    summary = {
        "blend": str(BLEND),
        "meaning": {
            "green_sphere": "actual UEFN joint head inside mesh",
            "red_sphere": "actual UEFN joint head outside mesh",
            "colored_line": "parent joint head to child joint head",
            "fbx_tail_locations": "not rendered",
        },
        "outside_joint_heads": sorted(
            name for name, values in report.items() if not values["inside_mesh"]
        ),
        "joints": report,
    }
    REPORT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("BOSS_JOINT_DIAGNOSTIC=" + json.dumps(summary["outside_joint_heads"]))
    print("BOSS_JOINT_DIAGNOSTIC_DIR=" + str(OUT_DIR))


if __name__ == "__main__":
    main()
