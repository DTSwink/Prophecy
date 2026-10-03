import json
import unreal


def safe_call(label, fn):
    try:
        return {"label": label, "ok": True, "value": fn()}
    except Exception as exc:
        return {"label": label, "ok": False, "error": repr(exc)}


def names(obj, needle=None, limit=300):
    out = []
    for name in dir(obj):
        if needle is None or needle.lower() in name.lower():
            out.append(name)
    return out[:limit]


bp = unreal.load_object(None, "/Game/_mygame/blood2/A_DecalManager.A_DecalManager")
ndc = unreal.load_object(None, "/Game/_mygame/blood2/NDC_test.NDC_test")
ns_render = unreal.load_object(None, "/Game/_mygame/blood2/NS_bloodrender.NS_bloodrender")

classes_to_probe = [
    "K2Node_WriteDataChannel",
    "K2Node_WriteDataChannel_WithContext",
    "K2Node_WriteDataChannelSingle_WithContext",
    "K2Node_DataChannelAccessContext_Make",
    "K2Node_CallFunction",
    "K2Node_CustomEvent",
    "K2Node_VariableGet",
    "K2Node_VariableSet",
    "EdGraph",
    "EdGraphNode",
    "EdGraphSchema_K2",
    "KismetCompilerLibrary",
    "BlueprintEditorLibrary",
    "NiagaraDataChannelLibrary",
    "NiagaraEditorLibrary",
    "NiagaraSystem",
    "NiagaraDataChannelAsset",
]

payload = {
    "asset_classes": {
        "bp": bp.get_class().get_name() if bp else None,
        "ndc": ndc.get_class().get_name() if ndc else None,
        "ns_render": ns_render.get_class().get_name() if ns_render else None,
    },
    "class_presence": {},
    "calls": [],
}

for class_name in classes_to_probe:
    cls = getattr(unreal, class_name, None)
    payload["class_presence"][class_name] = {
        "present": cls is not None,
        "dir_data": names(cls, "data") if cls is not None else [],
        "dir_node": names(cls, "node") if cls is not None else [],
        "dir_pin": names(cls, "pin") if cls is not None else [],
        "dir_graph": names(cls, "graph") if cls is not None else [],
        "dir_editor": names(cls, "editor") if cls is not None else [],
    }

if bp:
    payload["calls"].append(safe_call("bp_generated_class", lambda: str(bp.generated_class)))
    payload["calls"].append(safe_call("bp_variables", lambda: [str(v) for v in unreal.BlueprintEditorLibrary.get_blueprint_variable_list(bp)]))
    graph = None
    try:
        graph = unreal.BlueprintEditorLibrary.find_event_graph(bp)
    except Exception as exc:
        payload["calls"].append({"label": "find_event_graph", "ok": False, "error": repr(exc)})
    else:
        payload["calls"].append({"label": "find_event_graph", "ok": True, "value": str(graph)})
        payload["event_graph_class"] = graph.get_class().get_name() if graph else None
        payload["event_graph_dir_node"] = names(graph, "node")
        payload["event_graph_dir_graph"] = names(graph, "graph")
        payload["event_graph_dir_pin"] = names(graph, "pin")
        payload["event_graph_dir_add"] = names(graph, "add")
        payload["event_graph_dir_modify"] = names(graph, "modify")
        payload["event_graph_props"] = {}
        for prop in ["nodes", "schema", "sub_graphs"]:
            payload["event_graph_props"][prop] = safe_call(prop, lambda p=prop: str(graph.get_editor_property(p)))

        # Try creating a few node object types without adding them. This is non-mutating unless construction itself fails.
        for class_name in [
            "K2Node_WriteDataChannel",
            "K2Node_WriteDataChannel_WithContext",
            "K2Node_WriteDataChannelSingle_WithContext",
            "K2Node_CustomEvent",
            "K2Node_CallFunction",
        ]:
            cls = getattr(unreal, class_name, None)
            if cls is not None:
                payload["calls"].append(
                    safe_call(
                        "new_object_" + class_name,
                        lambda c=cls: str(unreal.new_object(c, graph)),
                    )
                )

if ndc:
    payload["ndc_dir"] = {
        "data": names(ndc, "data"),
        "variable": names(ndc, "variable"),
        "definition": names(ndc, "definition"),
        "props": names(ndc, None, 120),
    }
    payload["calls"].append(safe_call("ndc_export_text", lambda: ndc.export_text()))
    for prop in [
        "data_channel",
        "variables",
        "user_parameters",
        "data_channel_variables",
        "channel",
    ]:
        payload["calls"].append(safe_call("ndc_prop_" + prop, lambda p=prop: str(ndc.get_editor_property(p))))

if ns_render:
    payload["ns_render_dir"] = {
        "emitter": names(ns_render, "emitter"),
        "script": names(ns_render, "script"),
        "props": names(ns_render, None, 160),
    }
    for prop in ["emitter_handles", "system_spawn_script", "system_update_script", "exposed_parameters"]:
        payload["calls"].append(safe_call("ns_render_prop_" + prop, lambda p=prop: str(ns_render.get_editor_property(p))))

print("PROPHECY_BP_API_PROBE_BEGIN")
print(json.dumps(payload, indent=2, default=str))
print("PROPHECY_BP_API_PROBE_END")
