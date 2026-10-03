import unreal


for obj in unreal.ObjectIterator(unreal.K2Node_CallFunction):
    try:
        path = unreal.SystemLibrary.get_path_name(obj)
    except Exception:
        continue
    if "SandboxCharacter_CMC:EventGraph" not in path:
        continue
    print("NODE {}".format(path))
    for prop in ["function_reference", "pins", "node_pos_x", "node_pos_y", "node_comment"]:
        try:
            value = obj.get_editor_property(prop)
            print("  {} type={} value={}".format(prop, type(value), value))
            if prop == "pins":
                for pin in value:
                    print("    pin type={} dir={} name={} default={} links={}".format(
                        type(pin),
                        pin.get_editor_property("direction"),
                        pin.get_editor_property("pin_name"),
                        pin.get_editor_property("default_value"),
                        pin.get_editor_property("linked_to")))
        except Exception as error:
            print("  FAIL {} {}".format(prop, error))
    break

