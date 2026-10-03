import unreal


modifier = unreal.SkinWeightModifier()
for name in dir(modifier):
    if "weight" in name.lower() or "vertex" in name.lower() or "commit" in name.lower():
        value = getattr(modifier, name)
        print("SKIN_METHOD|{}|{}".format(name, getattr(value, "__doc__", "")))
