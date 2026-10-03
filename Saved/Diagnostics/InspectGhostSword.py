import unreal
mesh=unreal.load_asset('/Game/_mygame/sword/geometry/Sword_GL01_Training')
body=mesh.get_editor_property('body_setup')
agg=body.get_editor_property('agg_geom')
print('GHOST_SWORD_GEOMETRY',dict(boxes=len(agg.get_editor_property('box_elems')),
    convexes=[dict(vertices=len(c.get_editor_property('vertex_data')),indices=len(c.get_editor_property('index_data'))) for c in agg.get_editor_property('convex_elems')]))
