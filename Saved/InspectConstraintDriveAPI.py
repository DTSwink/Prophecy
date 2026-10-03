import unreal

names = [
    name for name in dir(unreal.ConstraintInstanceBlueprintLibrary)
    if any(token in name.lower() for token in ("angular", "drive", "swing", "twist", "broken"))
]
for name in names:
    member = getattr(unreal.ConstraintInstanceBlueprintLibrary, name)
    print(name + "=" + str(getattr(member, "__doc__", "")).splitlines()[0])
