import json
import os

import unreal

SOURCE_BODY = "/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh"

body = unreal.load_asset(SOURCE_BODY)
if not isinstance(body, unreal.SkeletalMesh):
    raise RuntimeError("Could not load source fitted body")

ppabp = body.get_editor_property("post_process_anim_blueprint")
print("SOURCE_PPABP|{}".format(ppabp.get_path_name() if ppabp else "None"))
skeleton = body.get_editor_property("skeleton")
print("SOURCE_SKELETON|{}".format(skeleton.get_path_name()))

snapshot_path = os.path.join(
    unreal.Paths.project_dir(), "Tools", "MetaHuman", "skeleton_snapshots.json"
)
with open(snapshot_path, "r", encoding="utf-8") as handle:
    snapshot = json.load(handle)
uefn_names = {entry["name"] for entry in snapshot["uefn_reference"]["bones"]}

modifier = unreal.SkinWeightModifier()
if not modifier.set_skeletal_mesh(body):
    raise RuntimeError("Could not inspect source body weights")

num_vertices = modifier.get_num_vertices()
totals = {}
counts = {}
max_w = {}
for vertex_id in range(num_vertices):
    for name, value in modifier.get_vertex_weights(vertex_id).items():
        key = str(name)
        weight = float(value)
        if weight <= 0.0001:
            continue
        totals[key] = totals.get(key, 0.0) + weight
        counts[key] = counts.get(key, 0) + 1
        if weight > max_w.get(key, 0.0):
            max_w[key] = weight

helper_rows = []
shared_total = 0.0
helper_total = 0.0
for name, total in totals.items():
    if name in uefn_names:
        shared_total += total
    else:
        helper_total += total
        helper_rows.append((total, name))

helper_rows.sort(reverse=True)
print("SOURCE_WEIGHTS|vertices={}|used_bones={}|shared_total={:.1f}|helper_total={:.1f}".format(
    num_vertices, len(totals), shared_total, helper_total))
for total, name in helper_rows:
    print("HELPER|{}|total={:.3f}|verts={}|max={:.3f}".format(
        name, total, counts[name], max_w[name]))
