import unreal


for name in dir(unreal):
    lower = name.lower()
    if "geometryscript" in lower and ("bone" in lower or "asset" in lower or "skeletal" in lower or "copy" in lower or "staticmesh" in lower):
        print("GEOMETRY_CLASS|{}".format(name))

for name in ("GeometryScript_AssetUtils", "GeometryScript_BoneWeights"):
    value = getattr(unreal, name, None)
    print("CLASS|{}|{}".format(name, value))
    if value:
        for method in dir(value):
            if "skeletal" in method.lower() or "bone" in method.lower() or "weight" in method.lower():
                print("METHOD|{}|{}|{}".format(name, method, getattr(value, method).__doc__))
