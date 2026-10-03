import json
import unreal


def cls(name):
    return getattr(unreal, name, None)


def full_dir(obj, limit=1000):
    try:
        return [n for n in dir(obj) if not n.startswith("__")][:limit]
    except Exception as exc:
        return ["ERROR: " + repr(exc)]


def safe(label, fn):
    try:
        return {"label": label, "ok": True, "value": fn()}
    except Exception as exc:
        return {"label": label, "ok": False, "error": repr(exc)}


bp = unreal.load_object(None, "/Game/_mygame/blood2/A_DecalManager.A_DecalManager")
graph = unreal.BlueprintEditorLibrary.find_event_graph(bp) if bp else None

payload = {}
for name in [
    "K2Node_CallFunction",
    "EdGraphNode",
    "EdGraph",
    "BlueprintEditorLibrary",
    "NiagaraDataChannelLibrary",
    "KismetSystemLibrary",
    "KismetMathLibrary",
]:
    c = cls(name)
    payload[name] = {
        "present": c is not None,
        "dir": full_dir(c, 500) if c else [],
    }

payload["graph_dir"] = full_dir(graph, 500) if graph else []
payload["calls"] = []

if graph and cls("K2Node_CallFunction"):
    node = unreal.new_object(unreal.K2Node_CallFunction, graph)
    payload["node_dir"] = full_dir(node, 500)
    payload["node_class"] = node.get_class().get_name()
    payload["calls"].append(safe("node_get_editor_property_node_pos_x", lambda: str(node.get_editor_property("node_pos_x"))))
    for prop in [
        "function_reference",
        "node_pos_x",
        "node_pos_y",
        "advanced_pin_display",
        "enabled_state",
        "node_comment",
        "b_comment_bubble_pinned",
        "b_comment_bubble_visible",
    ]:
        payload["calls"].append(safe("prop_" + prop, lambda p=prop: str(node.get_editor_property(p))))
    for method in [
        "set_from_function",
        "set_from_function_name",
        "allocate_default_pins",
        "reconstruct_node",
        "create_new_guid",
        "post_placed_new_node",
    ]:
        payload["calls"].append(safe("has_method_" + method, lambda m=method: callable(getattr(node, m, None))))

payload["library_functions"] = []
for fname in [
    "write_to_niagara_data_channel",
    "read_from_niagara_data_channel",
    "get_data_channel_element_count",
]:
    fn = getattr(unreal.NiagaraDataChannelLibrary, fname, None)
    payload["library_functions"].append({
        "name": fname,
        "present": fn is not None,
        "str": str(fn),
        "dir": full_dir(fn, 80) if fn else [],
    })

print("PROPHECY_K2_FUNCTION_PROBE_BEGIN")
print(json.dumps(payload, indent=2, default=str))
print("PROPHECY_K2_FUNCTION_PROBE_END")
