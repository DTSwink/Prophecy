import sys
import unreal


asset = unreal.EditorAssetLibrary.load_asset(sys.argv[1])
graph = unreal.BlueprintEditorLibrary.find_event_graph(asset)
print("GRAPH {} {}".format(graph, graph.get_class().get_name()))
print("GRAPH_DIR {}".format([
    name for name in dir(graph)
    if any(token in name.lower() for token in ["node", "pin", "graph", "object"])
]))
for property_name in ["nodes", "sub_graphs", "schema"]:
    try:
        print("PROPERTY {} = {}".format(property_name, graph.get_editor_property(property_name)))
    except Exception as error:
        print("PROPERTY_FAIL {} = {}".format(property_name, error))

