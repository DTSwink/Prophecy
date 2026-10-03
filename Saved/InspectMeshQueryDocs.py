import unreal


for name in ("get_all_vertex_positions", "get_vertex_position", "get_all_vertex_i_ds"):
    method = getattr(unreal.GeometryScript_MeshQueries, name)
    print("DOC|{}|{}".format(name, method.__doc__))
