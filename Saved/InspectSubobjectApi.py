import unreal

for cls in [unreal.SubobjectDataSubsystem, unreal.SubobjectDataBlueprintFunctionLibrary]:
    print("{} {}".format(cls, [
        name for name in dir(cls)
        if any(token in name.lower() for token in ["gather", "data", "object", "handle", "component"])
    ]))

