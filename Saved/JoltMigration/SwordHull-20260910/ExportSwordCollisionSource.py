import json
from pathlib import Path
import unreal

out = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/SwordHull-20260910/source.json'
assert not out.exists(), 'Source export already exists'
mesh = unreal.load_asset('/Game/_mygame/sword/geometry/Sword_GL01_Training')
assert mesh
description = mesh.get_static_mesh_description(0)
vertices = []
for index in range(description.get_vertex_count()):
    vertex = unreal.VertexID(index)
    assert description.is_vertex_valid(vertex), 'Unexpected sparse vertex IDs'
    p = description.get_vertex_position(vertex)
    vertices.append([p.x, p.y, p.z])
data = {'asset': mesh.get_path_name(), 'vertices_cm': vertices,
        'materials': [str(x.material_interface.get_path_name()) if x.material_interface else ''
                      for x in mesh.get_editor_property('static_materials')],
        'scope': 'Current Training LOD0 source positions, read only; no asset saves.'}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(data, indent=2))
print('SWORD_HULL_SOURCE_SUCCESS vertices=' + str(len(vertices)))
