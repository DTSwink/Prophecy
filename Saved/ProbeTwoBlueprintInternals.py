import json
import unreal

paths = [
    "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent",
    "/Game/_mygame/SandboxCharacter_CMC",
]

result = {}
for path in paths:
    bp = unreal.EditorAssetLibrary.load_asset(path)
    graph = unreal.BlueprintEditorLibrary.find_event_graph(bp)
    entry = {
        "bp_dir": [n for n in dir(bp) if any(k in n.lower() for k in ["construction", "component", "graph", "node", "class"])],
        "graph": str(graph),
        "graph_dir": [n for n in dir(graph) if any(k in n.lower() for k in ["node", "graph", "object", "export"])],
        "objects_direct": [],
        "objects_nested": [],
    }
    for nested, key in [(False, "objects_direct"), (True, "objects_nested")]:
        try:
            objects = unreal.get_objects_with_outer(graph, include_nested_objects=nested)
            entry[key] = ["{}:{}".format(o.get_class().get_name(), o.get_name()) for o in objects[:200]]
        except Exception as exc:
            entry[key] = ["ERROR {}".format(exc)]
    for prop in ["nodes", "sub_graphs", "schema"]:
        try:
            entry["graph_" + prop] = str(graph.get_editor_property(prop))
        except Exception as exc:
            entry["graph_" + prop] = "ERROR {}".format(exc)
    for prop in ["simple_construction_script", "ubergraph_pages", "function_graphs"]:
        try:
            value = bp.get_editor_property(prop)
            entry["bp_" + prop] = str(value)
            if prop == "simple_construction_script" and value:
                entry["scs_dir"] = [n for n in dir(value) if "node" in n.lower() or "root" in n.lower()]
        except Exception as exc:
            entry["bp_" + prop] = "ERROR {}".format(exc)
    result[path] = entry

print("TWO_BP_PROBE_BEGIN")
print(json.dumps(result, indent=2))
print("TWO_BP_PROBE_END")
