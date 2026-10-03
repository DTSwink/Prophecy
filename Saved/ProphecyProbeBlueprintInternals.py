import json
import unreal


def safe(label, fn):
    try:
        return {"label": label, "ok": True, "value": fn()}
    except Exception as exc:
        return {"label": label, "ok": False, "error": repr(exc)}


def small_dir(obj, needles):
    out = {}
    try:
        all_names = dir(obj)
        for needle in needles:
            out[needle] = [n for n in all_names if needle.lower() in n.lower()][:80]
    except Exception as exc:
        out["ERROR"] = repr(exc)
    return out


bp = unreal.load_object(None, "/Game/_mygame/blood2/A_DecalManager.A_DecalManager")
graph = unreal.BlueprintEditorLibrary.find_event_graph(bp) if bp else None

payload = {
    "unreal_helpers": {},
    "calls": [],
    "graph": str(graph),
}

for helper in [
    "get_objects_with_outer",
    "get_objects_of_class",
    "find_object",
    "load_object",
    "new_object",
    "duplicate_object",
]:
    obj = getattr(unreal, helper, None)
    payload["unreal_helpers"][helper] = {
        "present": obj is not None,
        "str": str(obj),
    }

objects = []
if graph and getattr(unreal, "get_objects_with_outer", None):
    try:
        raw = unreal.get_objects_with_outer(graph, include_nested_objects=True)
    except TypeError:
        raw = unreal.get_objects_with_outer(graph)
    except Exception as exc:
        payload["calls"].append({"label": "get_objects_with_outer", "ok": False, "error": repr(exc)})
        raw = []
    else:
        payload["calls"].append({"label": "get_objects_with_outer", "ok": True, "value": len(raw)})
    for obj in raw[:500]:
        item = {
            "name": obj.get_name(),
            "class": obj.get_class().get_name(),
            "path": obj.get_path_name(),
            "dir": small_dir(obj, ["pin", "node", "graph", "function", "default", "linked", "schema", "exec", "name"]),
        }
        # Try common editor-readable properties.
        props = {}
        for prop in [
            "pins",
            "node_pos_x",
            "node_pos_y",
            "node_guid",
            "custom_function_name",
            "function_reference",
            "delegate_output_name",
            "event_reference",
            "node_comment",
            "enabled_state",
        ]:
            try:
                props[prop] = str(obj.get_editor_property(prop))
            except Exception:
                pass
        item["props"] = props
        objects.append(item)

payload["objects_count"] = len(objects)
payload["objects"] = objects[:220]

print("PROPHECY_BP_INTERNALS_BEGIN")
print(json.dumps(payload, indent=2, default=str))
print("PROPHECY_BP_INTERNALS_END")
