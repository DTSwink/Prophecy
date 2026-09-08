"""Transfer the proven Ally2 weights to the full-body ``boss`` mesh.

This script is deliberately deterministic and safe to rerun:

* ``forcodex.blend`` is treated as immutable input.
* all spatial queries are evaluated in world space;
* body weights use nearest-face barycentric interpolation;
* the MetaHuman face/neck source is collapsed onto UEFN head/neck/body bones;
* the two sources are smoothly blended across their shared collar region;
* output weights are pruned to eight influences and normalized;
* the result is saved to a new .blend and audited at the rig's test frames.

Run with Blender:
    blender --background --factory-startup forcodex.blend \
        --python blender_transfer_boss_weights.py
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


INPUT = Path(r"C:\Users\singerie\Documents\Blender\forcodex.blend")
OUTPUT = Path(r"C:\Users\singerie\Documents\Blender\forcodex_BossWeighted.blend")
AUDIT = Path(
    r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
    r"\Saved\BlenderExchange\BossWeightTransfer_Audit.json"
)
SHOT_DIR = Path(
    r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
    r"\Saved\BlenderShots\BossWeightTransfer"
)

BODY_NAME = "ally2_Body_Mesh"
FACE_NAME = "ally2_Face_Mesh"
TARGET_NAME = "boss"
RIG_NAME = "UEFN_WORKING_CLEAN_RIG.001"
MAX_INFLUENCES = 8
MIN_WEIGHT = 1.0e-5


def require_object(name: str, object_type: str | None = None):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise RuntimeError(f"Required object is missing: {name}")
    if object_type and obj.type != object_type:
        raise RuntimeError(f"{name} is {obj.type}, expected {object_type}")
    return obj


def evaluated_world_mesh(obj):
    """Return stable world vertices and triangle indices at the current frame."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        if len(mesh.vertices) != len(obj.data.vertices):
            raise RuntimeError(
                f"{obj.name} evaluated topology changed: "
                f"{len(obj.data.vertices)} -> {len(mesh.vertices)} vertices"
            )
        mesh.calc_loop_triangles()
        vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
    finally:
        evaluated.to_mesh_clear()
    return vertices, triangles


def base_world_vertices(obj):
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]


def normalize(weights):
    total = sum(value for value in weights.values() if value > 0.0)
    if total <= 1.0e-12:
        return {}
    return {
        name: value / total
        for name, value in weights.items()
        if value > 0.0
    }


def body_vertex_weights(source, valid_bones):
    group_names = {group.index: group.name for group in source.vertex_groups}
    result = []
    for vertex in source.data.vertices:
        values = defaultdict(float)
        for membership in vertex.groups:
            name = group_names.get(membership.group)
            if name in valid_bones and membership.weight > 0.0:
                values[name] += membership.weight
        result.append(normalize(values))
    return result


def collapse_face_group(name: str, valid_bones):
    """Collapse MetaHuman's facial/neck helper groups to the UEFN body rig."""
    if name in valid_bones:
        return name

    lower = name.lower()
    side = "_l" if "_l_" in lower or lower.endswith("_l") else "_r"

    if "neckbackb" in lower or "neckb" in lower:
        return "neck_02"
    if "neckbacka" in lower or "necka" in lower or "adamsapple" in lower:
        return "neck_01"

    if name.startswith("FACIAL_"):
        return "head"

    if lower.startswith(("clavicle_pec_", "clavicle_out_", "clavicle_scap_")):
        candidate = "clavicle" + side
        return candidate if candidate in valid_bones else "spine_04"
    if lower.startswith(("upperarm_out_", "upperarm_fwd_", "upperarm_in_", "upperarm_bck_")):
        candidate = "upperarm" + side
        return candidate if candidate in valid_bones else "spine_04"
    if lower.startswith("spine_04_latissimus_"):
        return "spine_04"

    # The face source contains only face, neck, and shoulder deformation
    # groups. Unknown face helpers are safest when rigidly collapsed to head.
    return "head"


def face_vertex_weights(source, valid_bones):
    group_names = {group.index: group.name for group in source.vertex_groups}
    result = []
    for vertex in source.data.vertices:
        values = defaultdict(float)
        for membership in vertex.groups:
            if membership.weight <= 0.0:
                continue
            original = group_names.get(membership.group, "")
            mapped = collapse_face_group(original, valid_bones)
            if mapped in valid_bones:
                values[mapped] += membership.weight
        result.append(normalize(values))
    return result


def barycentric(point, a, b, c):
    """Barycentric coordinates of ``point`` on triangle ABC."""
    v0 = b - a
    v1 = c - a
    v2 = point - a
    d00 = v0.dot(v0)
    d01 = v0.dot(v1)
    d11 = v1.dot(v1)
    d20 = v2.dot(v0)
    d21 = v2.dot(v1)
    denominator = d00 * d11 - d01 * d01
    if abs(denominator) < 1.0e-18:
        return (1.0, 0.0, 0.0)
    v = (d11 * d20 - d01 * d21) / denominator
    w = (d00 * d21 - d01 * d20) / denominator
    u = 1.0 - v - w
    # BVH returns a point on the triangle, but clamp tiny numerical drift.
    values = [max(0.0, min(1.0, value)) for value in (u, v, w)]
    total = sum(values)
    if total <= 1.0e-12:
        return (1.0, 0.0, 0.0)
    return tuple(value / total for value in values)


class SurfaceWeightSampler:
    def __init__(self, world_vertices, triangles, vertex_weights):
        self.vertices = world_vertices
        self.triangles = triangles
        self.vertex_weights = vertex_weights
        self.bvh = BVHTree.FromPolygons(
            world_vertices, triangles, all_triangles=True
        )

    def sample(self, point):
        location, _normal, triangle_index, distance = self.bvh.find_nearest(point)
        if triangle_index is None:
            return {}, math.inf
        indices = self.triangles[triangle_index]
        factors = barycentric(
            location,
            self.vertices[indices[0]],
            self.vertices[indices[1]],
            self.vertices[indices[2]],
        )
        values = defaultdict(float)
        for vertex_index, factor in zip(indices, factors):
            for group_name, weight in self.vertex_weights[vertex_index].items():
                values[group_name] += factor * weight
        return normalize(values), float(distance)


def smoothstep(edge0, edge1, value):
    if edge1 <= edge0:
        return float(value >= edge1)
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def mix_and_limit(body_weights, face_weights, face_factor):
    values = defaultdict(float)
    for name, weight in body_weights.items():
        values[name] += (1.0 - face_factor) * weight
    for name, weight in face_weights.items():
        values[name] += face_factor * weight
    filtered = [
        (name, weight)
        for name, weight in values.items()
        if weight >= MIN_WEIGHT
    ]
    filtered.sort(key=lambda pair: pair[1], reverse=True)
    return normalize(dict(filtered[:MAX_INFLUENCES]))


def clear_target_rigging(target):
    target.parent = None
    for modifier in list(target.modifiers):
        if modifier.type == "ARMATURE":
            target.modifiers.remove(modifier)
    target.vertex_groups.clear()


def assign_weights(target, rig, all_weights):
    valid_bones = {bone.name for bone in rig.data.bones}
    groups = {
        name: target.vertex_groups.new(name=name)
        for name in sorted(valid_bones)
    }
    by_group = defaultdict(list)
    for vertex_index, weights in enumerate(all_weights):
        for name, weight in weights.items():
            by_group[name].append((vertex_index, weight))
    for name, assignments in by_group.items():
        group = groups[name]
        for vertex_index, weight in assignments:
            group.add([vertex_index], weight, "REPLACE")

    world_matrix = target.matrix_world.copy()
    target.parent = rig
    target.matrix_parent_inverse = rig.matrix_world.inverted()
    target.matrix_world = world_matrix

    modifier = target.modifiers.new(name="UEFN Working Rig", type="ARMATURE")
    modifier.object = rig
    modifier.use_vertex_groups = True
    modifier.use_bone_envelopes = False


def prepare_dynamic_smooth_normals(target):
    """Remove FBX rest-pose normals that facet after armature deformation."""
    mesh = target.data
    custom_normals = mesh.attributes.get("custom_normal")
    if custom_normals is not None:
        mesh.attributes.remove(custom_normals)
    sharp_edges = mesh.attributes.get("sharp_edge")
    if sharp_edges is not None:
        mesh.attributes.remove(sharp_edges)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    for edge in mesh.edges:
        edge.use_edge_sharp = False
    mesh.update()


def mesh_world_positions(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()
    return points


def bounds(points):
    minimum = [min(point[axis] for point in points) for axis in range(3)]
    maximum = [max(point[axis] for point in points) for axis in range(3)]
    return {
        "minimum": minimum,
        "maximum": maximum,
        "dimensions": [maximum[i] - minimum[i] for i in range(3)],
    }


def audit_vertex_groups(target, valid_bones):
    group_names = {group.index: group.name for group in target.vertex_groups}
    zero = 0
    max_sum_error = 0.0
    max_influences = 0
    unknown = set()
    used = set()
    for vertex in target.data.vertices:
        memberships = [
            membership
            for membership in vertex.groups
            if membership.weight > 1.0e-8
        ]
        total = sum(membership.weight for membership in memberships)
        zero += int(total <= 1.0e-8)
        if total > 1.0e-8:
            max_sum_error = max(max_sum_error, abs(total - 1.0))
        max_influences = max(max_influences, len(memberships))
        for membership in memberships:
            name = group_names[membership.group]
            used.add(name)
            if name not in valid_bones:
                unknown.add(name)
    return {
        "vertex_count": len(target.data.vertices),
        "weighted_vertices": len(target.data.vertices) - zero,
        "zero_weight_vertices": zero,
        "maximum_weight_sum_error": max_sum_error,
        "maximum_influences": max_influences,
        "used_groups": sorted(used),
        "unknown_groups": sorted(unknown),
    }


def create_readme(body_max_z, blend_start, blend_end):
    text = bpy.data.texts.get("BOSS_WEIGHT_TRANSFER_README")
    if text is None:
        text = bpy.data.texts.new("BOSS_WEIGHT_TRANSFER_README")
    text.clear()
    text.write(
        "Reusable Boss weight transfer\n"
        "=============================\n\n"
        "Target: boss\n"
        "Body weight source: ally2_Body_Mesh\n"
        "Head/neck source: ally2_Face_Mesh\n"
        "Armature: UEFN_WORKING_CLEAN_RIG.001\n\n"
        "Technique:\n"
        "- world-space nearest-face barycentric interpolation\n"
        "- MetaHuman facial groups collapse to head\n"
        "- Neck A groups collapse to neck_01; Neck B to neck_02\n"
        "- face/body sources blend smoothly through the collar\n"
        f"- body source maximum Z: {body_max_z:.9f} m\n"
        f"- collar blend: {blend_start:.9f} to {blend_end:.9f} m\n"
        f"- influences pruned to {MAX_INFLUENCES}, then normalized\n\n"
        "Re-run Tools/MetaHuman/blender_transfer_boss_weights.py from the\n"
        "Prophecy project to reproduce the result from forcodex.blend.\n"
    )


def look_at(camera, target):
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def configure_render(scene, target):
    scene.render.resolution_x = 720
    scene.render.resolution_y = 960
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.color_type = "SINGLE"
    scene.display.shading.single_color = (0.56, 0.61, 0.68)
    scene.world.color = (0.035, 0.035, 0.035)

    camera_data = bpy.data.cameras.new("BossTransferAuditCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 2.05
    camera = bpy.data.objects.new("BossTransferAuditCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    render_visibility = {obj.name: obj.hide_render for obj in bpy.context.scene.objects}
    for obj in bpy.context.scene.objects:
        obj.hide_render = obj != target
    target.hide_render = False
    return camera, render_visibility


def render_audits(scene, target, frame_positions):
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    camera, visibility = configure_render(scene, target)
    try:
        for frame, view in ((0, "Front"), (29, "Front"), (29, "Side")):
            scene.frame_set(frame)
            points = mesh_world_positions(target)
            box = bounds(points)
            center = Vector(
                tuple(
                    (box["minimum"][axis] + box["maximum"][axis]) * 0.5
                    for axis in range(3)
                )
            )
            if view == "Front":
                camera.location = center + Vector((0.0, -4.0, 0.0))
            else:
                camera.location = center + Vector((4.0, 0.0, 0.0))
            look_at(camera, center)
            scene.render.filepath = str(SHOT_DIR / f"Boss_Frame{frame}_{view}.png")
            bpy.ops.render.render(write_still=True)
            frame_positions[f"{frame}_{view}"] = {
                "bounds": box,
                "image": scene.render.filepath,
            }
    finally:
        for obj in bpy.context.scene.objects:
            if obj.name in visibility:
                obj.hide_render = visibility[obj.name]
        bpy.data.objects.remove(camera, do_unlink=True)


def main():
    loaded = Path(bpy.data.filepath)
    if loaded.resolve() != INPUT.resolve():
        raise RuntimeError(f"Refusing unexpected input file: {loaded}")
    if OUTPUT.resolve() == INPUT.resolve():
        raise RuntimeError("Output must not overwrite forcodex.blend")

    scene = bpy.context.scene
    body = require_object(BODY_NAME, "MESH")
    face = require_object(FACE_NAME, "MESH")
    target = require_object(TARGET_NAME, "MESH")
    rig = require_object(RIG_NAME, "ARMATURE")
    if len(target.data.vertices) != 11374:
        raise RuntimeError(
            f"Unexpected boss topology: {len(target.data.vertices)} vertices"
        )

    scene.frame_set(0)
    bpy.context.view_layer.update()
    valid_bones = {bone.name for bone in rig.data.bones}

    body_world, body_triangles = evaluated_world_mesh(body)
    face_world, face_triangles = evaluated_world_mesh(face)
    target_world = base_world_vertices(target)
    body_weights = body_vertex_weights(body, valid_bones)
    face_weights = face_vertex_weights(face, valid_bones)
    body_sampler = SurfaceWeightSampler(body_world, body_triangles, body_weights)
    face_sampler = SurfaceWeightSampler(face_world, face_triangles, face_weights)

    body_max_z = max(point.z for point in body_world)
    overlap_min_z = max(
        min(point.z for point in face_world),
        body_max_z - 0.040,
    )
    overlap_max_z = body_max_z + 0.040

    target_weights = []
    source_stats = {
        "maximum_body_distance": 0.0,
        "maximum_face_distance": 0.0,
        "face_dominant_vertices": 0,
        "body_dominant_vertices": 0,
        "blended_vertices": 0,
    }
    for point in target_world:
        sampled_body, body_distance = body_sampler.sample(point)
        sampled_face, face_distance = face_sampler.sample(point)
        face_factor = smoothstep(overlap_min_z, overlap_max_z, point.z)

        # Within the overlap band, geometry distance is an additional guard
        # against selecting the opposite surface across the shoulder opening.
        if 0.0 < face_factor < 1.0:
            distance_total = max(body_distance + face_distance, 1.0e-12)
            distance_face = body_distance / distance_total
            face_factor = 0.75 * face_factor + 0.25 * distance_face

        weights = mix_and_limit(sampled_body, sampled_face, face_factor)
        if not weights:
            raise RuntimeError("A boss vertex received no usable rig weights")
        target_weights.append(weights)
        source_stats["maximum_body_distance"] = max(
            source_stats["maximum_body_distance"], body_distance
        )
        source_stats["maximum_face_distance"] = max(
            source_stats["maximum_face_distance"], face_distance
        )
        if face_factor >= 0.95:
            source_stats["face_dominant_vertices"] += 1
        elif face_factor <= 0.05:
            source_stats["body_dominant_vertices"] += 1
        else:
            source_stats["blended_vertices"] += 1

    clear_target_rigging(target)
    assign_weights(target, rig, target_weights)
    prepare_dynamic_smooth_normals(target)
    create_readme(body_max_z, overlap_min_z, overlap_max_z)

    scene.frame_set(0)
    bpy.context.view_layer.update()
    frame_zero = mesh_world_positions(target)
    scene.frame_set(29)
    bpy.context.view_layer.update()
    frame_test = mesh_world_positions(target)
    displacements = [
        (after - before).length
        for before, after in zip(frame_zero, frame_test)
    ]
    moved_threshold = 0.001
    deformation = {
        "frame_zero_bounds": bounds(frame_zero),
        "frame_29_bounds": bounds(frame_test),
        "maximum_vertex_displacement": max(displacements),
        "mean_vertex_displacement": sum(displacements) / len(displacements),
        "vertices_moved_over_1mm": sum(
            distance > moved_threshold for distance in displacements
        ),
    }

    weight_audit = audit_vertex_groups(target, valid_bones)
    if weight_audit["zero_weight_vertices"]:
        raise RuntimeError("Unweighted boss vertices remain")
    if weight_audit["unknown_groups"]:
        raise RuntimeError("Boss contains non-UEFN weight groups")
    if weight_audit["maximum_influences"] > MAX_INFLUENCES:
        raise RuntimeError("Boss exceeds the influence limit")
    if weight_audit["maximum_weight_sum_error"] > 1.0e-5:
        raise RuntimeError("Boss weights are not normalized")
    if deformation["vertices_moved_over_1mm"] == 0:
        raise RuntimeError("Rig test frame produced no boss deformation")

    scene.frame_set(0)
    bpy.context.view_layer.update()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT), check_existing=False)

    render_data = {}
    render_audits(scene, target, render_data)
    scene.frame_set(0)

    report = {
        "input_blend": str(INPUT),
        "output_blend": str(OUTPUT),
        "source_body": BODY_NAME,
        "source_face": FACE_NAME,
        "target": TARGET_NAME,
        "rig": RIG_NAME,
        "method": "world-space nearest-face barycentric, dual body/face source",
        "body_maximum_z": body_max_z,
        "blend_start_z": overlap_min_z,
        "blend_end_z": overlap_max_z,
        "source_statistics": source_stats,
        "weight_audit": weight_audit,
        "deformation_audit": deformation,
        "renders": render_data,
    }
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("BOSS_WEIGHT_TRANSFER_COMPLETE=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
