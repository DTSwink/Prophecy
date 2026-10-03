import unreal

for name in dir(unreal.ConstraintInstanceBlueprintLibrary):
    if "current" in name.lower():
        member = getattr(unreal.ConstraintInstanceBlueprintLibrary, name)
        print(name + "=" + str(getattr(member, "__doc__", "")).splitlines()[0])
