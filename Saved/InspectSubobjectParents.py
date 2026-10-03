import unreal


subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
library = unreal.SubobjectDataBlueprintFunctionLibrary
print("LIBRARY_METHODS {}".format([name for name in dir(library) if "parent" in name.lower() or "handle" in name.lower() or "name" in name.lower()]))
for path in [
    "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent",
    "/Game/_mygame/SandboxCharacter_CMC",
]:
    blueprint = unreal.EditorAssetLibrary.load_asset(path)
    print("BLUEPRINT {}".format(path))
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(blueprint):
        data = subsystem.k2_find_subobject_data_from_handle(handle)
        obj = library.get_object(data) or library.get_associated_object(data)
        if not obj:
            continue
        print("  object={} class={} data={}".format(obj.get_name(), obj.get_class().get_name(), data))
        for name in ["get_display_name", "get_variable_name", "get_parent_handle", "is_component", "is_root_component"]:
            if not hasattr(library, name):
                continue
            try:
                print("    {}={}".format(name, getattr(library, name)(data)))
            except Exception as error:
                print("    {} error={}".format(name, error))
        try:
            parent_handle = library.get_parent_handle(data)
            parent_data = subsystem.k2_find_subobject_data_from_handle(parent_handle)
            parent_object = library.get_object(parent_data) or library.get_associated_object(parent_data)
            print("    parent_object={}".format(parent_object.get_name() if parent_object else None))
        except Exception as error:
            print("    parent_object error={}".format(error))
