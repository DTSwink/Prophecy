import unreal,json
m=unreal.load_asset('/Game/_mygame/sword/geometry/Sword_GL01')
d=m.get_static_mesh_description(0)
v=[d.get_vertex_position(unreal.VertexID(i)) for i in range(d.get_vertex_count())]
blade=[p for p in v if 25<p.z<65]
print(json.dumps({'blade_vertices':len(blade),'bounds':{a:[min(getattr(p,a) for p in blade),max(getattr(p,a) for p in blade)] for a in ['x','y','z']}}))
