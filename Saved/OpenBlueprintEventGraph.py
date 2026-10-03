import sys
import unreal

path = sys.argv[1]
asset = unreal.EditorAssetLibrary.load_asset(path)
if not asset:
    raise RuntimeError("Missing asset " + path)
unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([asset])
graph = unreal.BlueprintEditorLibrary.find_event_graph(asset)
methods = [name for name in dir(unreal.BlueprintEditorLibrary) if "graph" in name.lower() or "open" in name.lower()]
print("GRAPH_METHODS {}".format(methods))
if hasattr(unreal.BlueprintEditorLibrary, "open_graph_and_bring_to_front"):
    unreal.BlueprintEditorLibrary.open_graph_and_bring_to_front(graph)
    print("OPENED_EVENT_GRAPH {}".format(path))
