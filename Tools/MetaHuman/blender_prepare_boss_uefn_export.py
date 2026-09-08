"""Build a correctly bound Boss export on the native UEFN skeleton.

The artist-facing working rig uses a fitted MetaHuman pose while the hidden
UEFN_NATIVE_EXPORT_RIG retains the authoritative UEFN reference skeleton.
The finished fitted Boss surface is converted back through the fitted UEFN
pose into that native bind pose, then exported with the untouched native
joint layout.  This keeps the joints inside the mesh and permits direct use of
animations authored for the same UEFN skeleton.

Material regions are also repaired into stable body/face slots so Unreal can
reassign the original MetaHuman material instances.  The artist's
bossfinalsave.blend is never overwritten.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
SOURCE = Path(r"C:\Users\singerie\Documents\Blender\bossfinalsave.blend")
OUTPUT_DIR = PROJECT / "Saved" / "BlenderExchange" / "BossUEFN"
OUTPUT_BLEND = OUTPUT_DIR / "Boss_UEFN_ExportClean.blend"
OUTPUT_FBX = OUTPUT_DIR / "SKM_Boss_UEFN.fbx"
OUTPUT_AUDIT = OUTPUT_DIR / "Boss_UEFN_ExportAudit.json"
REFERENCE_BLEND = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "FourCharacters"
    / "BP_boss_Meshes.blend"
)
REFERENCE_BODY_NAME = "BP_boss_Body_Mesh"
REFERENCE_FACE_NAME = "BP_boss_Face_Mesh"

TARGET_NAME = "boss"
WORKING_RIG_NAME = "UEFN_WORKING_CLEAN_RIG.001"
NATIVE_RIG_NAME = "UEFN_NATIVE_EXPORT_RIG"
EXPORT_MESH_NAME = "SKM_Boss_UEFN"
EXPORT_RIG_NAME = "root"
EXPECTED_BONES = 87
EXPECTED_VERTICES = 11374
MAX_INFLUENCES = 8

# The combined Boss mesh retained all face/body polygon regions, but Blender's
# join left their material labels shifted.  The polygon counts identify the
# original MetaHuman regions unambiguously.
MATERIAL_LAYOUT = (
    ("body_shader_shader", 7, 15196),
    ("teeth_shader_shader", 0, 796),
    ("eyeLeft_shader_shader", 1, 216),
    ("eyeRight_shader_shader", 2, 216),
    ("eyeshell_shader_shader", 3, 196),
    ("eyeEdge_shader_shader", 4, 150),
    ("eyelashes_HiLOD_shader_shader", 5, 250),
    ("head_LOD3_shader_shader", 6, 5048),
)

sys.path.insert(0, str(Path(__file__).parent))
from blender_ue_export import export_skeletal_fbx, ensure_cm_scene


def require_object(name, object_type):
    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != object_type:
        raise RuntimeError(f"Missing {object_type} object: {name}")
    return obj


def matrix_max_delta(left, right):
    return max(
        abs(left[row][column] - right[row][column])
        for row in range(4)
        for column in range(4)
    )


def hierarchy(rig):
    return {
        bone.name: bone.parent.name if bone.parent else None
        for bone in rig.data.bones
    }


def evaluated_world_positions(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        if len(mesh.vertices) != len(obj.data.vertices):
            raise RuntimeError(
                f"{obj.name} evaluated topology changed "
                f"({len(obj.data.vertices)} -> {len(mesh.vertices)})"
            )
        return [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def normalized_vertex_weights(mesh, valid_bones):
    index_to_name = {
        group.index: group.name
        for group in mesh.vertex_groups
        if group.name in valid_bones
    }
    result = []
    for vertex in mesh.data.vertices:
        values = {
            index_to_name[membership.group]: membership.weight
            for membership in vertex.groups
            if membership.group in index_to_name and membership.weight > 1.0e-10
        }
        total = sum(values.values())
        if total <= 1.0e-10:
            raise RuntimeError(f"Unweighted Boss vertex: {vertex.index}")
        ordered = sorted(values.items(), key=lambda item: item[1], reverse=True)
        ordered = ordered[:MAX_INFLUENCES]
        total = sum(weight for _name, weight in ordered)
        result.append({name: weight / total for name, weight in ordered})
    return result


def write_normalized_weights(mesh, weights, valid_bones):
    for group in list(mesh.vertex_groups):
        if group.name not in valid_bones:
            mesh.vertex_groups.remove(group)
    groups = {
        name: mesh.vertex_groups.get(name) or mesh.vertex_groups.new(name=name)
        for name in sorted(valid_bones)
    }
    for group in groups.values():
        group.remove(range(len(mesh.data.vertices)))
    for vertex_index, values in enumerate(weights):
        for name, weight in values.items():
            groups[name].add([vertex_index], weight, "REPLACE")


def bake_finished_surface(mesh, desired_world):
    object_world_inverse = mesh.matrix_world.inverted_safe()
    for vertex, finished_world in zip(mesh.data.vertices, desired_world):
        vertex.co = object_world_inverse @ finished_world
    mesh.data.update()


def remove_armature_modifiers(mesh):
    for modifier in list(mesh.modifiers):
        if modifier.type == "ARMATURE":
            mesh.modifiers.remove(modifier)


def repair_material_regions(mesh):
    old_indices = [polygon.material_index for polygon in mesh.data.polygons]
    old_to_new = {
        old_index: new_index
        for new_index, (_name, old_index, _count) in enumerate(MATERIAL_LAYOUT)
    }
    unknown = sorted(set(old_indices) - set(old_to_new))
    if unknown:
        raise RuntimeError(f"Unexpected Boss material indices: {unknown}")

    mesh.data.materials.clear()
    for name, _old_index, _count in MATERIAL_LAYOUT:
        material = bpy.data.materials.get(name)
        if material is None:
            material = bpy.data.materials.new(name=name)
        mesh.data.materials.append(material)

    for polygon, old_index in zip(mesh.data.polygons, old_indices):
        polygon.material_index = old_to_new[old_index]
    mesh.data.update()

    counts = [
        sum(polygon.material_index == index for polygon in mesh.data.polygons)
        for index in range(len(MATERIAL_LAYOUT))
    ]
    expected = [count for _name, _old_index, count in MATERIAL_LAYOUT]
    if counts != expected:
        raise RuntimeError(
            f"Boss material-region audit failed: {counts} != {expected}"
        )
    return [
        {
            "index": index,
            "slot_name": name,
            "polygon_count": counts[index],
        }
        for index, (name, _old_index, _count) in enumerate(MATERIAL_LAYOUT)
    ]


def material_vertices(mesh, material_index):
    return {
        vertex
        for polygon in mesh.data.polygons
        if polygon.material_index == material_index
        for vertex in polygon.vertices
    }


def vertex_weight_map(mesh, vertex_index):
    group_names = {group.index: group.name for group in mesh.vertex_groups}
    return {
        group_names[item.group]: item.weight
        for item in mesh.data.vertices[vertex_index].groups
        if item.weight > 1.0e-10
    }


def write_vertex_weights(mesh, vertex_index, values):
    for group in mesh.vertex_groups:
        group.remove([vertex_index])
    for name, weight in values.items():
        mesh.vertex_groups[name].add([vertex_index], weight, "REPLACE")


def close_body_face_seam(mesh):
    """Close and shade-match the duplicated MetaHuman Body/Face border.

    The joined source contains a 46-point body collar and a matching 46-point
    face ring. They are separated by up to 1.5 mm and have independently
    calculated normals. The rings carry virtually identical weights. Averaging
    their positions/weights closes the gap while deliberately retaining every
    polygon and both UV seams; their loop normals are matched separately after
    smoothing. Welding the topology is unsafe because the source has a thin
    transition strip whose degenerate faces would be deleted.
    """

    body_vertices = material_vertices(mesh, 0)
    face_vertices = material_vertices(mesh, 7)
    face_tree = KDTree(len(face_vertices))
    for vertex_index in face_vertices:
        face_tree.insert(mesh.data.vertices[vertex_index].co, vertex_index)
    face_tree.balance()
    body_tree = KDTree(len(body_vertices))
    for vertex_index in body_vertices:
        body_tree.insert(mesh.data.vertices[vertex_index].co, vertex_index)
    body_tree.balance()

    pairs = []
    for body_index in body_vertices:
        _position, face_index, distance = face_tree.find(
            mesh.data.vertices[body_index].co
        )
        if distance > 1.0:  # full collar; mesh-local units are centimeters
            continue
        _position, reverse_body, _distance = body_tree.find(
            mesh.data.vertices[face_index].co
        )
        if reverse_body == body_index:
            pairs.append((body_index, face_index, distance))
    if (
        len(pairs) != 46
        or len({body for body, _face, _distance in pairs}) != 46
        or len({face for _body, face, _distance in pairs}) != 46
    ):
        raise RuntimeError(
            "Body/Face seam is not the expected one-to-one 46-vertex ring"
        )

    maximum_displacement_cm = 0.0
    maximum_weight_l1 = 0.0
    for body_index, face_index, distance in pairs:
        midpoint = (
            mesh.data.vertices[body_index].co
            + mesh.data.vertices[face_index].co
        ) * 0.5
        maximum_displacement_cm = max(
            maximum_displacement_cm, distance * 0.5
        )
        body_weights = vertex_weight_map(mesh, body_index)
        face_weights = vertex_weight_map(mesh, face_index)
        names = set(body_weights) | set(face_weights)
        maximum_weight_l1 = max(
            maximum_weight_l1,
            sum(
                abs(body_weights.get(name, 0.0) - face_weights.get(name, 0.0))
                for name in names
            ),
        )
        averaged = {
            name: 0.5 * (
                body_weights.get(name, 0.0) + face_weights.get(name, 0.0)
            )
            for name in names
        }
        total = sum(averaged.values())
        averaged = {
            name: weight / total
            for name, weight in averaged.items()
            if weight > 1.0e-10
        }
        mesh.data.vertices[body_index].co = midpoint
        mesh.data.vertices[face_index].co = midpoint
        write_vertex_weights(mesh, body_index, averaged)
        write_vertex_weights(mesh, face_index, averaged)

    mesh.data.update()
    seam_points_world = [
        mesh.matrix_world @ mesh.data.vertices[body_index].co
        for body_index, _face_index, _distance in pairs
    ]
    report = {
        "pair_count": len(pairs),
        "maximum_original_gap_cm": max(distance for _b, _f, distance in pairs),
        "maximum_surface_displacement_cm": maximum_displacement_cm,
        "maximum_original_weight_l1": maximum_weight_l1,
        "result_vertex_count": len(mesh.data.vertices),
    }
    return (
        report,
        [(body, face) for body, face, _distance in pairs],
        seam_points_world,
    )


def weld_closed_body_face_seam(mesh, pairs):
    vertices_before = len(mesh.data.vertices)
    polygons_before = len(mesh.data.polygons)
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.verts.ensure_lookup_table()
    target_map = {
        bm.verts[face_index]: bm.verts[body_index]
        for body_index, face_index in pairs
        if body_index != face_index
    }
    bmesh.ops.weld_verts(bm, targetmap=target_map)
    bm.to_mesh(mesh.data)
    bm.free()
    mesh.data.update()
    return {
        "vertices_before": vertices_before,
        "vertices_after": len(mesh.data.vertices),
        "vertices_removed": vertices_before - len(mesh.data.vertices),
        "polygons_before": polygons_before,
        "polygons_after": len(mesh.data.polygons),
        "collapsed_polygons_removed": polygons_before - len(mesh.data.polygons),
    }


def smooth_welded_body_face_geometry(mesh):
    """Remove the real surface kink at the welded MetaHuman collar.

    Matching split normals cannot hide the collar under MetaHuman skin
    materials because their normal/roughness response exposes the underlying
    15-30 degree geometric turn.  Apply a small Taubin-style relaxation to
    only the welded ring and its first three topological neighbours.  The
    fourth ring is the fixed boundary, and the negative pass limits shrinkage.
    """

    body_vertices = material_vertices(mesh, 0)
    face_vertices = material_vertices(mesh, 7)
    skin_vertices = body_vertices | face_vertices
    shared = body_vertices & face_vertices
    if len(shared) != 46:
        raise RuntimeError(
            "Cannot smooth collar without 46 shared boundary vertices"
        )

    adjacency = {index: set() for index in skin_vertices}
    for edge in mesh.data.edges:
        first, second = edge.vertices
        if first in skin_vertices and second in skin_vertices:
            adjacency[first].add(second)
            adjacency[second].add(first)

    distance = {index: 0 for index in shared}
    frontier = set(shared)
    for ring in range(1, 5):
        next_frontier = set()
        for index in frontier:
            next_frontier.update(
                neighbor
                for neighbor in adjacency[index]
                if neighbor not in distance
            )
        for index in next_frontier:
            distance[index] = ring
        frontier = next_frontier

    falloff = {0: 1.0, 1: 0.70, 2: 0.38, 3: 0.16}
    movable = {
        index: falloff[ring]
        for index, ring in distance.items()
        if ring in falloff
    }
    original = {
        index: mesh.data.vertices[index].co.copy() for index in movable
    }

    def relax(factor):
        positions = [vertex.co.copy() for vertex in mesh.data.vertices]
        updates = {}
        for index, weight in movable.items():
            neighbors = adjacency[index]
            if not neighbors:
                continue
            average = Vector((0.0, 0.0, 0.0))
            for neighbor in neighbors:
                average += positions[neighbor]
            average /= len(neighbors)
            updates[index] = (
                positions[index]
                + (average - positions[index]) * factor * weight
            )
        for index, position in updates.items():
            mesh.data.vertices[index].co = position

    for _iteration in range(5):
        relax(0.46)
        relax(-0.48)
    mesh.data.update()

    displacements = [
        (mesh.data.vertices[index].co - original[index]).length
        for index in movable
    ]
    ring_counts = {
        str(ring): sum(1 for value in distance.values() if value == ring)
        for ring in range(5)
    }
    return {
        "method": "weighted_taubin_collar_relaxation",
        "iterations": 5,
        "rings": ring_counts,
        "moved_vertices": len(movable),
        "maximum_displacement_cm": max(displacements, default=0.0),
        "mean_displacement_cm": (
            sum(displacements) / len(displacements) if displacements else 0.0
        ),
    }


def match_shared_body_face_normals(mesh):
    mesh.data.update()
    custom_normals = [
        item.vector.copy() for item in mesh.data.corner_normals
    ]
    shared = material_vertices(mesh, 0) & material_vertices(mesh, 7)
    if len(shared) != 46:
        raise RuntimeError(
            "Welded Body/Face boundary is not 46 shared vertices: "
            + str(len(shared))
        )
    loops_by_vertex = defaultdict(list)
    for polygon in mesh.data.polygons:
        if polygon.material_index not in (0, 7):
            continue
        for loop_index in polygon.loop_indices:
            loop = mesh.data.loops[loop_index]
            if loop.vertex_index in shared:
                loops_by_vertex[loop.vertex_index].append(loop_index)

    matched_loops = 0
    maximum_angle_before = 0.0
    for loop_indices in loops_by_vertex.values():
        normals = [
            mesh.data.corner_normals[index].vector.copy()
            for index in loop_indices
        ]
        for left in normals:
            for right in normals:
                dot = max(-1.0, min(1.0, left.dot(right)))
                maximum_angle_before = max(
                    maximum_angle_before, math.degrees(math.acos(dot))
                )
        average = Vector((0.0, 0.0, 0.0))
        for normal in normals:
            average += normal
        average.normalize()
        for loop_index in loop_indices:
            custom_normals[loop_index] = average
            matched_loops += 1
    mesh.data.normals_split_custom_set(custom_normals)
    mesh.data.update()
    return {
        "matched_vertices": len(shared),
        "matched_loops": matched_loops,
        "maximum_normal_angle_before_deg": maximum_angle_before,
        "target_normal_angle_deg": 0.0,
    }


def load_reference_normal_meshes():
    if not REFERENCE_BLEND.is_file():
        raise RuntimeError("Missing authored Boss normal reference")
    with bpy.data.libraries.load(str(REFERENCE_BLEND), link=False) as (
        data_from,
        data_to,
    ):
        required = {REFERENCE_BODY_NAME, REFERENCE_FACE_NAME}
        missing = required - set(data_from.objects)
        if missing:
            raise RuntimeError("Missing reference objects: " + str(missing))
        data_to.objects = [REFERENCE_BODY_NAME, REFERENCE_FACE_NAME]
    loaded = {obj.name: obj for obj in data_to.objects if obj is not None}
    for obj in loaded.values():
        bpy.context.scene.collection.objects.link(obj)
        obj.hide_set(False)
        obj.hide_viewport = False
        # The mesh-only reference retains its 0.01 centimeter wrapper scale;
        # a dependency-graph update is required after library loading before
        # matrix_world reflects it.
    bpy.context.view_layer.update()
    body = loaded[REFERENCE_BODY_NAME]
    face = loaded[REFERENCE_FACE_NAME]
    body.name = "BOSS_AUTHORED_NORMAL_REFERENCE_BODY"
    face.name = "BOSS_AUTHORED_NORMAL_REFERENCE_FACE"
    return body, face


def world_bvh(obj):
    vertices = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    polygons = [list(polygon.vertices) for polygon in obj.data.polygons]
    return BVHTree.FromPolygons(vertices, polygons, all_triangles=False)


def seam_band_weights(mesh, seam_points, material_index, inner_m, outer_m):
    material_vertex_set = material_vertices(mesh, material_index)
    weights = {}
    for vertex_index in material_vertex_set:
        position = mesh.matrix_world @ mesh.data.vertices[vertex_index].co
        distance = min((position - point).length for point in seam_points)
        if distance >= outer_m:
            continue
        if distance <= inner_m:
            weight = 1.0
        else:
            t = (distance - inner_m) / (outer_m - inner_m)
            # Smoothstep falloff avoids creating a second normal boundary.
            weight = 1.0 - t * t * (3.0 - 2.0 * t)
        weights[vertex_index] = weight
    return weights


def transfer_reference_normals(mesh, source, weights, group_name):
    group = mesh.vertex_groups.get(group_name)
    if group is not None:
        mesh.vertex_groups.remove(group)
    group = mesh.vertex_groups.new(name=group_name)
    for vertex_index, weight in weights.items():
        group.add([vertex_index], weight, "REPLACE")

    source_bvh = world_bvh(source)
    distances = []
    weighted_distances = []
    for vertex_index, transfer_weight in weights.items():
        position = mesh.matrix_world @ mesh.data.vertices[vertex_index].co
        nearest = source_bvh.find_nearest(position)
        if nearest is None:
            raise RuntimeError("Authored normal reference query failed")
        distances.append(nearest[3])
        weighted_distances.append(nearest[3] * transfer_weight)
    if (
        max(distances, default=0.0) > 0.035
        or max(weighted_distances, default=0.0) > 0.015
    ):
        source_points = [
            source.matrix_world @ vertex.co for vertex in source.data.vertices
        ]
        target_points = [
            mesh.matrix_world @ mesh.data.vertices[index].co for index in weights
        ]
        raise RuntimeError(
            "Authored normal reference is too far from the seam band: "
            + str(
                {
                    "maximum_distance": max(distances),
                    "source_bounds": [
                        [min(p[axis] for p in source_points) for axis in range(3)],
                        [max(p[axis] for p in source_points) for axis in range(3)],
                    ],
                    "target_band_bounds": [
                        [min(p[axis] for p in target_points) for axis in range(3)],
                        [max(p[axis] for p in target_points) for axis in range(3)],
                    ],
                }
            )
        )

    modifier = mesh.modifiers.new(
        name="Transfer Authored MetaHuman Normals", type="DATA_TRANSFER"
    )
    modifier.object = source
    modifier.use_loop_data = True
    modifier.data_types_loops = {"CUSTOM_NORMAL"}
    modifier.loop_mapping = "POLYINTERP_NEAREST"
    modifier.mix_mode = "REPLACE"
    modifier.mix_factor = 1.0
    modifier.vertex_group = group.name
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    remaining_group = mesh.vertex_groups.get(group_name)
    if remaining_group is not None:
        mesh.vertex_groups.remove(remaining_group)
    return {
        "weighted_vertices": len(weights),
        "maximum_reference_surface_distance_m": max(distances, default=0.0),
        "maximum_weighted_reference_distance_m": max(
            weighted_distances, default=0.0
        ),
        "mean_reference_surface_distance_m": (
            sum(distances) / len(distances) if distances else 0.0
        ),
    }


def restore_authored_seam_band_normals(mesh, seam_points):
    body_reference, face_reference = load_reference_normal_meshes()
    try:
        body_weights = seam_band_weights(
            mesh, seam_points, 0, inner_m=0.025, outer_m=0.090
        )
        face_weights = seam_band_weights(
            mesh, seam_points, 7, inner_m=0.015, outer_m=0.050
        )
        report = {
            "body_inner_full_strength_radius_m": 0.025,
            "body_outer_falloff_radius_m": 0.090,
            "face_inner_full_strength_radius_m": 0.015,
            "face_outer_falloff_radius_m": 0.050,
            "body": transfer_reference_normals(
                mesh,
                body_reference,
                body_weights,
                "__BOSS_BODY_NORMAL_BAND__",
            ),
            "face": transfer_reference_normals(
                mesh,
                face_reference,
                face_weights,
                "__BOSS_FACE_NORMAL_BAND__",
            ),
        }
    finally:
        for obj in (body_reference, face_reference):
            bpy.data.objects.remove(obj, do_unlink=True)
    return report


def bind_to_native(mesh, native_rig):
    for modifier in list(mesh.modifiers):
        if modifier.type == "ARMATURE":
            mesh.modifiers.remove(modifier)
    modifier = mesh.modifiers.new(name="UEFN Native Skeleton", type="ARMATURE")
    modifier.object = native_rig
    modifier.use_vertex_groups = True
    modifier.use_bone_envelopes = False
    modifier.use_deform_preserve_volume = False

    world = mesh.matrix_world.copy()
    mesh.parent = native_rig
    mesh.matrix_parent_inverse = native_rig.matrix_world.inverted_safe()
    mesh.matrix_world = world


def prepare_smooth_normals(mesh):
    custom_normal = mesh.data.attributes.get("custom_normal")
    if custom_normal:
        mesh.data.attributes.remove(custom_normal)
    sharp_edge = mesh.data.attributes.get("sharp_edge")
    if sharp_edge:
        mesh.data.attributes.remove(sharp_edge)
    for polygon in mesh.data.polygons:
        polygon.use_smooth = True
    for edge in mesh.data.edges:
        edge.use_edge_sharp = False
    mesh.data.update()


def weight_audit(mesh, valid_bones):
    group_names = {group.index: group.name for group in mesh.vertex_groups}
    zero = 0
    maximum_influences = 0
    maximum_sum_error = 0.0
    unknown = set()
    for vertex in mesh.data.vertices:
        memberships = [
            membership
            for membership in vertex.groups
            if membership.weight > 1.0e-8
        ]
        total = sum(membership.weight for membership in memberships)
        zero += int(total <= 1.0e-8)
        maximum_influences = max(maximum_influences, len(memberships))
        if total > 1.0e-8:
            maximum_sum_error = max(maximum_sum_error, abs(total - 1.0))
        for membership in memberships:
            name = group_names[membership.group]
            if name not in valid_bones:
                unknown.add(name)
    return {
        "vertices": len(mesh.data.vertices),
        "zero_weight_vertices": zero,
        "maximum_influences": maximum_influences,
        "maximum_weight_sum_error": maximum_sum_error,
        "unknown_groups": sorted(unknown),
    }


def position_delta(left, right):
    distances = [(a - b).length for a, b in zip(left, right)]
    return {
        "maximum_m": max(distances),
        "rms_m": math.sqrt(
            sum(distance * distance for distance in distances) / len(distances)
        ),
        "mean_m": sum(distances) / len(distances),
    }


def clear_pose(rig):
    rig.animation_data_clear()
    for pose_bone in rig.pose.bones:
        pose_bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def inverse_skin_to_native_rest(mesh, rig, fitted_world_positions):
    """Solve the linear-blend skinning equation for native-rest vertices."""

    rig_world = rig.matrix_world.copy()
    rig_world_inverse = rig_world.inverted_safe()
    deformation = {}
    for bone in rig.data.bones:
        pose_bone = rig.pose.bones[bone.name]
        deformation[bone.name] = (
            rig_world
            @ pose_bone.matrix
            @ bone.matrix_local.inverted_safe()
            @ rig_world_inverse
        )

    group_names = {
        group.index: group.name for group in mesh.vertex_groups
    }
    rest_world_positions = []
    maximum_condition_warning = 0.0
    for vertex, fitted_world in zip(
        mesh.data.vertices, fitted_world_positions
    ):
        memberships = [
            (group_names[item.group], item.weight)
            for item in vertex.groups
            if (
                item.group in group_names
                and group_names[item.group] in deformation
                and item.weight > 1.0e-10
            )
        ]
        total = sum(weight for _name, weight in memberships)
        if total <= 1.0e-10:
            raise RuntimeError(
                "Cannot inverse-skin unweighted vertex "
                + str(vertex.index)
            )
        rows = [[0.0] * 4 for _row in range(4)]
        for name, raw_weight in memberships:
            weight = raw_weight / total
            matrix = deformation[name]
            for row in range(4):
                for column in range(4):
                    rows[row][column] += matrix[row][column] * weight
        blended = Matrix(rows)
        determinant = abs(blended.to_3x3().determinant())
        maximum_condition_warning = max(
            maximum_condition_warning,
            1.0 / max(determinant, 1.0e-12),
        )
        rest_world_positions.append(
            blended.inverted_safe() @ fitted_world
        )

    world_inverse = mesh.matrix_world.inverted_safe()
    for vertex, rest_world in zip(
        mesh.data.vertices, rest_world_positions
    ):
        vertex.co = world_inverse @ rest_world
    mesh.data.update()
    return {
        "method": "per_vertex_inverse_linear_blend_skinning",
        "vertices": len(rest_world_positions),
        "maximum_inverse_determinant_indicator": maximum_condition_warning,
    }


def detach_preserving_world(obj):
    world = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = world


def remove_everything_except(keep):
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def add_readme(audit):
    text = bpy.data.texts.get("README_BOSS_UEFN_EXPORT")
    if text is None:
        text = bpy.data.texts.new("README_BOSS_UEFN_EXPORT")
    text.clear()
    text.write(
        "BOSS - NATIVE UEFN SKELETAL EXPORT\n\n"
        "This clean file contains only:\n"
        "- root: authoritative native-rest 87-bone UEFN armature\n"
        "- SKM_Boss_UEFN: finished, normalized Boss mesh\n\n"
        "The artist-facing fitted Blender rig is intentionally absent.\n"
        "The fitted surface was inverse-skinned into the native UEFN bind pose\n"
        "before binding. Bone names, hierarchy, reference transforms, and FBX\n"
        "axes are unchanged. Do not apply Automatic Bone Orientation or edit\n"
        "this rest skeleton before Unreal export.\n\n"
        + json.dumps(audit, indent=2, sort_keys=True)
    )


def main():
    if Path(bpy.data.filepath).resolve() != SOURCE.resolve():
        raise RuntimeError(f"Unexpected source file: {bpy.data.filepath}")
    scene = bpy.context.scene
    scene.frame_set(0)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    boss = require_object(TARGET_NAME, "MESH")
    working_rig = require_object(WORKING_RIG_NAME, "ARMATURE")
    native_rig = require_object(NATIVE_RIG_NAME, "ARMATURE")
    if len(boss.data.vertices) != EXPECTED_VERTICES:
        raise RuntimeError(
            f"Unexpected Boss topology: {len(boss.data.vertices)} vertices"
        )
    if len(native_rig.data.bones) != EXPECTED_BONES:
        raise RuntimeError(
            f"Unexpected native skeleton: {len(native_rig.data.bones)} bones"
        )

    working_names = {bone.name for bone in working_rig.data.bones}
    native_names = {bone.name for bone in native_rig.data.bones}
    if working_names != native_names:
        raise RuntimeError("Working/native bone-name sets differ")
    if hierarchy(working_rig) != hierarchy(native_rig):
        raise RuntimeError("Working/native bone hierarchies differ")

    desired_world = evaluated_world_positions(boss)
    weights = normalized_vertex_weights(boss, native_names)
    pose_basis_maximum = max(
        matrix_max_delta(pose_bone.matrix_basis, Matrix.Identity(4))
        for pose_bone in native_rig.pose.bones
    )
    if pose_basis_maximum < 1.0e-4:
        raise RuntimeError("Native fitted pose is unexpectedly absent")

    # Preserve the evaluated artist-facing surface verbatim.  Rebinding named
    # weights to another armature must not alter neutral geometry.
    bake_finished_surface(boss, desired_world)
    remove_armature_modifiers(boss)
    write_normalized_weights(boss, weights, native_names)
    material_report = repair_material_regions(boss)
    seam_report, seam_pairs, seam_points = close_body_face_seam(boss)
    seam_report["topology_weld"] = weld_closed_body_face_seam(
        boss, seam_pairs
    )
    seam_report["geometric_smoothing"] = smooth_welded_body_face_geometry(
        boss
    )
    seam_points = [
        boss.matrix_world @ boss.data.vertices[index].co
        for index in (
            material_vertices(boss, 0) & material_vertices(boss, 7)
        )
    ]
    finished_world_after_seam_close = [
        boss.matrix_world @ vertex.co for vertex in boss.data.vertices
    ]
    inverse_skin_report = inverse_skin_to_native_rest(
        boss, native_rig, finished_world_after_seam_close
    )
    # Normals authored in the fitted surface cannot be reused after solving
    # the mesh back into the native bind pose. Recalculate smooth rest normals,
    # then explicitly match loops across the welded Body/Face boundary.
    prepare_smooth_normals(boss)
    seam_report["normal_match"] = match_shared_body_face_normals(boss)
    bind_to_native(boss, native_rig)

    fitted_pose_reconstruction = position_delta(
        finished_world_after_seam_close,
        evaluated_world_positions(boss),
    )
    if fitted_pose_reconstruction["maximum_m"] > 2.0e-5:
        raise RuntimeError(
            "Inverse skin did not reconstruct the fitted surface: "
            + str(fitted_pose_reconstruction)
        )

    weights_report = weight_audit(boss, native_names)
    if (
        weights_report["zero_weight_vertices"]
        or weights_report["unknown_groups"]
        or weights_report["maximum_influences"] > MAX_INFLUENCES
        or weights_report["maximum_weight_sum_error"] > 1.0e-5
    ):
        raise RuntimeError("Boss weight audit failed: " + str(weights_report))

    # The clean scene must contain the true native UEFN reference pose.
    clear_pose(native_rig)
    detach_preserving_world(native_rig)
    bpy.context.view_layer.update()
    native_rest_world = evaluated_world_positions(boss)
    geometry_preservation = fitted_pose_reconstruction

    # The imported Unreal FBX was carried by a 0.01 Blender wrapper.  After
    # detaching that wrapper the rig still has object scale 0.01.  The shared
    # exporter already declares a centimeter scene, so leaving this scale in
    # place would create a 1.65 cm character in Unreal.  Promote the root
    # object back to scale 1.0; its child mesh follows, yielding ~165 cm in the
    # centimeter export without changing the physical character size.
    native_rig.scale = tuple(value * 100.0 for value in native_rig.scale)
    bpy.context.view_layer.update()

    boss.name = EXPORT_MESH_NAME
    boss.data.name = EXPORT_MESH_NAME + "_Geometry"
    native_rig.name = EXPORT_RIG_NAME
    native_rig.data.name = "UEFN_Native_Export_Armature"
    native_rig.hide_set(False)
    native_rig.hide_viewport = False
    native_rig.hide_render = False
    boss.hide_set(False)
    boss.hide_viewport = False
    boss.hide_render = False
    remove_everything_except({boss, native_rig})
    ensure_cm_scene()
    scene.frame_start = 0
    scene.frame_end = 0
    scene.frame_set(0)

    audit = {
        "source_blend": str(SOURCE),
        "output_blend": str(OUTPUT_BLEND),
        "output_fbx": str(OUTPUT_FBX),
        "mesh": EXPORT_MESH_NAME,
        "rig": EXPORT_RIG_NAME,
        "bone_count": len(native_rig.data.bones),
        "bone_names": [bone.name for bone in native_rig.data.bones],
        "hierarchy": hierarchy(native_rig),
        "native_fitted_pose_basis_maximum": pose_basis_maximum,
        "centimeter_wrapper_scale_promoted": 100.0,
        "geometry_method": (
            "inverse_skin_fitted_surface_to_native_uefn_bind_pose_then_"
            "close_and_normal_match_metahuman_body_face_border"
        ),
        "inverse_skin_to_native_rest": inverse_skin_report,
        "fitted_pose_reconstruction": fitted_pose_reconstruction,
        "neutral_geometry_preservation": geometry_preservation,
        "body_face_seam_close": seam_report,
        "materials": material_report,
        "native_rest_bounds_m": {
            "minimum": [
                min(point[axis] for point in native_rest_world)
                for axis in range(3)
            ],
            "maximum": [
                max(point[axis] for point in native_rest_world)
                for axis in range(3)
            ],
        },
        "weight_audit": weights_report,
        "clean_scene_object_names": sorted(obj.name for obj in bpy.data.objects),
    }
    add_readme(audit)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND), check_existing=False)
    export_skeletal_fbx(str(OUTPUT_FBX), native_rig, [boss])
    if not OUTPUT_FBX.is_file() or OUTPUT_FBX.stat().st_size < 100_000:
        raise RuntimeError("FBX export is missing or implausibly small")
    audit["fbx_bytes"] = OUTPUT_FBX.stat().st_size
    OUTPUT_AUDIT.write_text(
        json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        "BOSS_UEFN_EXPORT_COMPLETE="
        + json.dumps(
            {
                "blend": str(OUTPUT_BLEND),
                "fbx": str(OUTPUT_FBX),
                "audit": str(OUTPUT_AUDIT),
                "geometry_preservation_maximum_m": geometry_preservation[
                    "maximum_m"
                ],
                "fbx_bytes": OUTPUT_FBX.stat().st_size,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    # The production path uses the already-correct Boss skin and a temporary
    # disconnected bind driver. Keep this file as the stable user-facing
    # entrypoint used by the documented PowerShell command.
    from blender_prepare_boss_uefn_export_driver import main as driver_main

    driver_main()
