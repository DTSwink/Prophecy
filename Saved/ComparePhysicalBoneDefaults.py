import unreal

for path in [
    "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent",
    "/Game/_mygame/SandboxCharacter_CMC",
]:
    cls = unreal.EditorAssetLibrary.load_blueprint_class(path)
    defaults = unreal.get_default_object(cls)
    names = [name for name in dir(defaults) if "physical" in name.lower() or "bone" in name.lower()]
    print("{} names={}".format(path, names))
    for candidate in ["physical_bones", "physical bones"]:
        try:
            print("  {}={}".format(candidate, defaults.get_editor_property(candidate)))
        except Exception as exc:
            print("  {} ERROR {}".format(candidate, exc))
