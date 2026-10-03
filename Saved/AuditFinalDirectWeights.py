import json
import os

import unreal


body = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody")
modifier = unreal.SkinWeightModifier()
if not modifier.set_skeletal_mesh(body):
    raise RuntimeError("Could not inspect final body weights")
with open(os.path.join(unreal.Paths.project_dir(), "Tools", "MetaHuman", "skeleton_snapshots.json"), "r", encoding="utf-8") as handle:
    snapshot = json.load(handle)
kept = {entry["name"] for entry in snapshot["uefn_reference"]["bones"]} - set(snapshot["fit_recipe"]["uefn_only_bones"])

used_names = set()
transition_counts = {"l": 0, "r": 0}
rigid_lowerarm = {"l": 0, "r": 0}
rigid_hand = {"l": 0, "r": 0}
for vertex_id in range(modifier.get_num_vertices()):
    weights = {str(name): float(value) for name, value in modifier.get_vertex_weights(vertex_id).items() if float(value) > 0.0001}
    used_names.update(weights)
    for side in ("l", "r"):
        lower = weights.get("lowerarm_" + side, 0.0)
        hand = weights.get("hand_" + side, 0.0)
        if lower > 0.001 and hand > 0.001:
            transition_counts[side] += 1
        if lower > 0.99:
            rigid_lowerarm[side] += 1
        if hand > 0.99:
            rigid_hand[side] += 1

unexpected = sorted(used_names - kept)
print("FINAL_WEIGHT_AUDIT|vertices={}|used_bones={}|unexpected={}".format(
    modifier.get_num_vertices(), len(used_names), len(unexpected)))
print("FINAL_WEIGHT_NAMES|unexpected={}".format(",".join(unexpected)))
for side in ("l", "r"):
    print("FINAL_WRIST|{}|transition={}|rigid_lowerarm={}|rigid_hand={}".format(
        side, transition_counts[side], rigid_lowerarm[side], rigid_hand[side]))
