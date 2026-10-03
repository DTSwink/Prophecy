import sys
import unreal


asset_path = sys.argv[1]
blueprint = unreal.EditorAssetLibrary.load_asset(asset_path)
if not blueprint:
    raise RuntimeError("Missing blueprint " + asset_path)
event_graph = unreal.BlueprintEditorLibrary.find_event_graph(blueprint)
prefix = event_graph.get_path_name() + "."
print("K2_CLASSES {}".format([
    name for name in dir(unreal)
    if name.startswith("K2Node") or name in ["EdGraphNode", "EdGraphPin"]
]))

objects = []
for obj in unreal.ObjectIterator(unreal.Object):
    try:
        path = obj.get_path_name()
    except TypeError:
        try:
            path = unreal.SystemLibrary.get_path_name(obj)
        except Exception:
            continue
    if path.startswith(prefix):
        objects.append((obj.get_class().get_name(), obj.get_name(), path, obj))
print("GRAPH={} OBJECTS={}".format(event_graph.get_path_name(), len(objects)))
for class_name, name, path, obj in sorted(objects):
    print("{} {} outer={}".format(class_name, path, obj.get_outer()))
    print("  DIR {}".format([
        item for item in dir(obj)
        if any(token in item.lower() for token in ["pin", "function", "variable", "node", "event"])
    ]))
