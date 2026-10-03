import unreal


path = "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent"
blueprint = unreal.EditorAssetLibrary.load_asset(path)
print("CLASS", blueprint.get_class().get_name())
print("DIR", [name for name in dir(blueprint) if "graph" in name.lower() or "uber" in name.lower() or "function" in name.lower()])
for prop in ["ubergraph_pages", "function_graphs", "delegate_signature_graphs", "macro_graphs", "simple_construction_script"]:
    try:
        value = blueprint.get_editor_property(prop)
        print("PROP", prop, value)
    except Exception as error:
        print("PROP_ERROR", prop, error)
try:
    graph = unreal.BlueprintEditorLibrary.find_event_graph(blueprint)
    print("FIND", graph)
    print("GRAPH_DIR", [name for name in dir(graph) if "node" in name.lower() or "graph" in name.lower()])
    print("LIB_DIR", [name for name in dir(unreal.BlueprintEditorLibrary) if "node" in name.lower() or "graph" in name.lower()])
except Exception as error:
    print("FIND_ERROR", error)
