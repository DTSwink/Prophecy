import json
import math
import os

import unreal


SOURCE_PATH = "/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh"
DIRECT_PATH = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody_HandFixTest"
SNAPSHOT_PATH = os.path.join(
    unreal.Paths.project_dir(), "Tools", "MetaHuman", "skeleton_snapshots.json"
)


def load_asset(path):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise RuntimeError(f"Could not load {path}")
    return asset


with open(SNAPSHOT_PATH, "r", encoding="utf-8") as handle:
    snapshot = json.load(handle)

source_bones = snapshot["fitted_metahuman_body_reference"]["bones"]
uefn_bones = snapshot["uefn_reference"]["bones"]
source_by_name = {bone["name"]: bone for bone in source_bones}
kept_names = {bone["name"] for bone in uefn_bones} & set(source_by_name)


def nearest_kept_ancestor(name):
    parent = source_by_name[name]["parent"]
    while parent is not None and parent not in kept_names:
        parent = source_by_name[parent]["parent"]
    return parent


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


kept_positions = {
    name: source_by_name[name]["global"]["translation_cm"] for name in kept_names
}


def nearest_kept_origin(name):
    position = source_by_name[name]["global"]["translation_cm"]
    return min(
        kept_positions,
        key=lambda candidate: distance(position, kept_positions[candidate]),
    )


source_modifier = unreal.SkinWeightModifier()
if not source_modifier.set_skeletal_mesh(load_asset(SOURCE_PATH)):
    raise RuntimeError("Could not read source skin weights")

direct_modifier = unreal.SkinWeightModifier()
if not direct_modifier.set_skeletal_mesh(load_asset(DIRECT_PATH)):
    raise RuntimeError("Could not read direct skin weights")

stats = {}
destination_stats = {}
affected_vertices = set()
max_weight_l1_error = 0.0
max_weight_l1_vertex = -1
weight_mismatch_vertices = 0
for vertex_index in range(source_modifier.get_num_vertices()):
    weights = source_modifier.get_vertex_weights(vertex_index)
    expected_weights = {}
    for bone_name, weight in weights.items():
        name = str(bone_name)
        destination = name if name in kept_names else nearest_kept_ancestor(name)
        successor = None
        if name not in kept_names:
            if "_01_half_" in name:
                candidate = name.replace("_01_half_", "_02_")
                successor = candidate if candidate in kept_names else None
            elif "_02_half_" in name:
                candidate = name.replace("_02_half_", "_03_")
                successor = candidate if candidate in kept_names else None
        if successor:
            expected_weights[destination] = expected_weights.get(destination, 0.0) + float(weight) * 0.5
            expected_weights[successor] = expected_weights.get(successor, 0.0) + float(weight) * 0.5
        else:
            expected_weights[destination] = expected_weights.get(destination, 0.0) + float(weight)
        if name in kept_names:
            continue
        nearest = nearest_kept_origin(name)
        row = stats.setdefault(
            name,
            {
                "weight": 0.0,
                "vertices": 0,
                "max_weight": 0.0,
                "destination": destination,
                "nearest": nearest,
            },
        )
        row["weight"] += float(weight)
        row["vertices"] += 1
        row["max_weight"] = max(row["max_weight"], float(weight))
        if destination:
            destination_row = destination_stats.setdefault(
                destination, {"weight": 0.0, "vertices": set(), "bones": set()}
            )
            destination_row["weight"] += float(weight)
            destination_row["vertices"].add(vertex_index)
            destination_row["bones"].add(name)
        affected_vertices.add(vertex_index)

    actual_weights = {
        str(name): float(weight)
        for name, weight in direct_modifier.get_vertex_weights(vertex_index).items()
    }
    all_names = set(expected_weights) | set(actual_weights)
    l1_error = sum(
        abs(expected_weights.get(name, 0.0) - actual_weights.get(name, 0.0))
        for name in all_names
    )
    if l1_error > 1.0e-4:
        weight_mismatch_vertices += 1
    if l1_error > max_weight_l1_error:
        max_weight_l1_error = l1_error
        max_weight_l1_vertex = vertex_index

print(
    "HAND_WEIGHT_AUDIT_COUNTS"
    f"|source_vertices={source_modifier.get_num_vertices()}"
    f"|direct_vertices={direct_modifier.get_num_vertices()}"
    f"|removed_influence_vertices={len(affected_vertices)}"
    f"|removed_weight_bones={len(stats)}"
)
print(
    "HAND_WEIGHT_AUDIT_ROUNDTRIP"
    f"|mismatch_vertices={weight_mismatch_vertices}"
    f"|max_l1={max_weight_l1_error:.9f}"
    f"|max_vertex={max_weight_l1_vertex}"
)

interesting_destinations = {
    name
    for name in kept_names
    if name.startswith(("lowerarm_", "hand_", "thumb_", "index_", "middle_", "ring_", "pinky_"))
}

print("HAND_WEIGHT_AUDIT_DESTINATIONS")
for destination, row in sorted(
    destination_stats.items(), key=lambda item: item[1]["weight"], reverse=True
):
    if destination not in interesting_destinations:
        continue
    print(
        f"DEST|{destination}|weight_sum={row['weight']:.6f}"
        f"|vertices={len(row['vertices'])}|removed_bones={len(row['bones'])}"
    )

print("HAND_WEIGHT_AUDIT_HELPERS")
for name, row in sorted(stats.items(), key=lambda item: item[1]["weight"], reverse=True):
    destination = row["destination"]
    if destination not in interesting_destinations:
        continue
    source_position = source_by_name[name]["global"]["translation_cm"]
    destination_distance = distance(source_position, kept_positions[destination])
    nearest_distance = distance(source_position, kept_positions[row["nearest"]])
    print(
        f"HELPER|{name}|to={destination}|nearest={row['nearest']}"
        f"|weight_sum={row['weight']:.6f}|vertices={row['vertices']}"
        f"|max={row['max_weight']:.6f}|to_dist_cm={destination_distance:.4f}"
        f"|nearest_dist_cm={nearest_distance:.4f}"
    )

print("HAND_WEIGHT_AUDIT_COMPLETE")
