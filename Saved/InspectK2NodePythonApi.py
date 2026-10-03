import unreal

for cls in [unreal.EdGraphNode, unreal.K2Node, unreal.K2Node_CallFunction]:
    print("CLASS {} DIR {}".format(cls, [
        name for name in dir(cls)
        if not name.startswith("_")
    ]))

for obj in unreal.ObjectIterator(unreal.K2Node_CallFunction):
    try:
        path = unreal.SystemLibrary.get_path_name(obj)
    except Exception:
        continue
    if "SandboxCharacter_CMC:EventGraph" not in path:
        continue
    print("OBJECT {} type={} isinstance={} dir={}".format(
        path, type(obj), isinstance(obj, unreal.K2Node_CallFunction),
        [name for name in dir(obj) if not name.startswith("_")]))
    break

