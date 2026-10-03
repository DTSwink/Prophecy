import unreal


for name in dir(unreal):
    if name.startswith("GeometryScript_"):
        value = getattr(unreal, name)
        methods = [method for method in dir(value) if "vertex" in method.lower() or "position" in method.lower()]
        if methods:
            print("QUERY_CLASS|{}|{}".format(name, ",".join(methods)))
