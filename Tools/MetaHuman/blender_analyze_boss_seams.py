"""Analyze disconnected shells and near-coincident seam vertices on Boss."""

import json
from collections import defaultdict, deque
from pathlib import Path

import bpy
from mathutils.kdtree import KDTree


OUT = Path(
    r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
    r"\Saved\BlenderExchange\BossUEFN\Boss_SeamTopologyAudit.json"
)
MESH_NAME = "boss"
EPSILONS_M = (1.0e-6, 1.0e-5, 1.0e-4, 5.0e-4, 1.0e-3)


def components(mesh):
    adjacency = [[] for _ in mesh.vertices]
    for edge in mesh.edges:
        left, right = edge.vertices
        adjacency[left].append(right)
        adjacency[right].append(left)
    unseen = set(range(len(mesh.vertices)))
    result = []
    while unseen:
        seed = unseen.pop()
        queue = deque([seed])
        component = [seed]
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
                    component.append(neighbor)
        result.append(component)
    result.sort(key=len, reverse=True)
    return result


def bounds(points):
    return {
        "minimum": [min(point[axis] for point in points) for axis in range(3)],
        "maximum": [max(point[axis] for point in points) for axis in range(3)],
    }


def main():
    obj = bpy.data.objects.get(MESH_NAME)
    if obj is None or obj.type != "MESH":
        raise RuntimeError("Missing Boss mesh")
    world = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    shells = components(obj.data)
    vertex_shell = {}
    for shell_index, shell in enumerate(shells):
        for vertex_index in shell:
            vertex_shell[vertex_index] = shell_index

    tree = KDTree(len(world))
    for index, point in enumerate(world):
        tree.insert(point, index)
    tree.balance()

    near_reports = {}
    for epsilon in EPSILONS_M:
        pairs = set()
        vertices = set()
        cross_shell_pairs = set()
        for index, point in enumerate(world):
            for _location, other, distance in tree.find_range(point, epsilon):
                if other <= index or distance > epsilon:
                    continue
                pair = (index, other)
                pairs.add(pair)
                vertices.update(pair)
                if vertex_shell[index] != vertex_shell[other]:
                    cross_shell_pairs.add(pair)
        near_reports[str(epsilon)] = {
            "pairs": len(pairs),
            "vertices": len(vertices),
            "cross_shell_pairs": len(cross_shell_pairs),
            "sample_cross_shell_pairs": list(sorted(cross_shell_pairs))[:50],
        }

    material_polygons = defaultdict(int)
    for polygon in obj.data.polygons:
        material_polygons[str(polygon.material_index)] += 1

    report = {
        "blend": bpy.data.filepath,
        "mesh": obj.name,
        "vertices": len(obj.data.vertices),
        "edges": len(obj.data.edges),
        "polygons": len(obj.data.polygons),
        "shell_count": len(shells),
        "shells": [
            {
                "index": index,
                "vertices": len(shell),
                "bounds": bounds([world[vertex] for vertex in shell]),
            }
            for index, shell in enumerate(shells)
        ],
        "near_coincident": near_reports,
        "material_polygon_counts": dict(material_polygons),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(
        "BOSS_SEAM_AUDIT="
        + json.dumps(
            {
                "shell_count": report["shell_count"],
                "shell_sizes": [len(shell) for shell in shells],
                "near_coincident": near_reports,
                "output": str(OUT),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
