import unreal

print("UNREAL_OBJECT_APIS {}".format([
    name for name in dir(unreal)
    if any(token in name.lower() for token in ["object", "iterator", "outer", "package"])
]))
for class_name in ["Object", "EditorAssetLibrary", "SystemLibrary", "KismetSystemLibrary"]:
    cls = getattr(unreal, class_name, None)
    if cls:
        print("{} {}".format(class_name, [
            name for name in dir(cls)
            if any(token in name.lower() for token in ["object", "outer", "export", "path", "name"])
        ]))

