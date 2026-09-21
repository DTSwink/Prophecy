import unreal; print([x for x in dir(unreal) if "CollisionResponse" in x]); print(unreal.CollisionResponseType.__dict__)
