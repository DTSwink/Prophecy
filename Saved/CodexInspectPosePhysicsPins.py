import unreal


base = "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent:EventGraph.K2Node_CallFunction_"
for index in range(40):
    node = unreal.load_object(None, base + str(index))
    if not node:
        continue
    print("FOUND", index, node.get_class().get_name())
    if index == 17:
        print("NODE_DIR", [name for name in dir(node) if "export" in name.lower() or "text" in name.lower() or "pin" in name.lower()])
    try:
        function_ref = node.get_editor_property("function_reference")
        member_name = str(function_ref)
    except Exception as error:
        member_name = "ERROR " + str(error)
    print("FUNCTION", index, member_name)
    if index not in {5, 10, 13, 16}:
        continue
    print("NODE", index, member_name)
    try:
        pins = node.get_editor_property("pins")
    except Exception as error:
        print("PINS_ERROR", error)
        continue
    for pin in pins:
        try:
            print(
                "PIN",
                pin.get_editor_property("pin_name"),
                "default=", pin.get_editor_property("default_value"),
                "links=", len(pin.get_editor_property("linked_to")),
            )
        except Exception as error:
            print("PIN_ERROR", error)
