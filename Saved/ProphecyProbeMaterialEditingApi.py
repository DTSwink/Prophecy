import unreal


names = [
    name
    for name in dir(unreal.MaterialEditingLibrary)
    if "connect" in name.lower()
    or "expression" in name.lower()
    or "input" in name.lower()
    or "property" in name.lower()
    or "delete" in name.lower()
]
unreal.log("[ProphecyMaterialEditingProbe] " + str(names))
