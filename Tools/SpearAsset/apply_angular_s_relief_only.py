"""Blender MCP entry point. Only the two allowed S relief meshes may change.

Prepared offline. Does not save, export, render, touch textures, or run modifiers.
"""
import bpy
import hashlib
import json
from pathlib import Path

ROOT = Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
OUT = ROOT/'Saved/Diagnostics/ImperialSpear/HandleFinish'
payload = json.loads((OUT/'Angular_S_Relief.json').read_text(encoding='utf-8'))
baseline = json.loads((OUT/'Accepted_Baseline.json').read_text(encoding='utf-8'))
art = bpy.data.collections['SPEAR \u2022 editable components']


def digest(data):
    return hashlib.sha256(json.dumps(data, separators=(',', ':')).encode()).hexdigest()


def snapshot(ob):
    mesh = ob.data
    return {'geometry': digest({'vertices': [list(v.co) for v in mesh.vertices],
                                'faces': [list(p.vertices) for p in mesh.polygons]}),
            'uv': digest([list(u.uv) for u in mesh.uv_layers['UV0_SurfaceAtlas'].data]),
            'all_uv': {uv.name: digest([list(u.uv) for u in uv.data]) for uv in mesh.uv_layers},
            'material_names': [m.name if m else None for m in mesh.materials],
            'material_indices': [p.material_index for p in mesh.polygons],
            'corner_normals': digest([list(n.vector) for n in mesh.corner_normals]),
            'transform': [list(r) for r in ob.matrix_world],
            'modifiers': [(m.name, m.type) for m in ob.modifiers]}


objects = {o.name: o for o in art.objects if o.type == 'MESH'}
before = {n: snapshot(o) for n, o in objects.items()}
assert len(payload['objects']) == 2
for name, data in payload['objects'].items():
    assert name.startswith('Socket \u2022 continuous cast inverted S')
    ob = objects[name]
    mesh = ob.data
    assert mesh.users == 1, ('Refuse shared mesh mutation', name, mesh.users)
    assert before[name]['geometry'] == data['source_geometry_sha256']
    assert before[name]['uv'] == data['source_uv_sha256']
    assert before[name]['geometry'] == baseline[name]['geometry']
    assert before[name]['uv'] == baseline[name]['uv']
    assert [uv.name for uv in mesh.uv_layers] == ['UV0_SurfaceAtlas'], ('Unexpected source UV layers',name)
    assert len(set(before[name]['material_indices'])) == 1

backups = {name: objects[name].data for name in payload['objects']}
new_meshes = []
try:
    for name, data in payload['objects'].items():
        old_mesh = backups[name]
        mesh = bpy.data.meshes.new(old_mesh.name+' Angular clean facets')
        new_meshes.append(mesh)
        mesh.from_pydata(data['vertices'], [], data['faces'])
        mesh.update()
        for material in old_mesh.materials:
            mesh.materials.append(material)
        uv = mesh.uv_layers.new(name='UV0_SurfaceAtlas')
        uv.active_render = True
        assert len(uv.data) == len(data['uv_loops'])
        for loop, value in zip(uv.data, data['uv_loops']):
            loop.uv = value
        # The S alone gets clean constrained triangulation and interpolated UVs.
        # Hard cross-section joins retain broad angular facets.
        for p in mesh.polygons:
            p.use_smooth = True
            p.material_index = before[name]['material_indices'][0]
        mesh.update()
        normals = []
        for p in mesh.polygons:
            source_face = data['faces'][p.index]
            for li in p.loop_indices:
                vi = mesh.loops[li].vertex_index
                normals.append(tuple(data['corner_normals'][p.index][source_face.index(vi)]))
        mesh.normals_split_custom_set(normals)
        mesh.update()
        objects[name].data = mesh
    bpy.context.view_layer.update()
    after = {n: snapshot(o) for n, o in objects.items()}
    for name in before:
        if name not in payload['objects']:
            assert after[name] == before[name], ('Protected component changed', name)
        else:
            assert after[name]['geometry'] == payload['objects'][name]['result_geometry_sha256']
            for k in ('material_names','transform','modifiers'):
                assert after[name][k] == before[name][k], ('S protected state changed',name,k)
            assert after[name]['uv'] == digest(payload['objects'][name]['uv_loops'])
    report = {'modified_objects': list(payload['objects']),
              'protected_components_identical': len(before)-2,
              'protected_uv_layers_identical': True, 'S_uv_interpolated_from_original': True,
              'materials_and_transforms_identical': True,
              'validation': {n: d['report'] for n,d in payload['objects'].items()}}
    (OUT/'Angular_S_Relief_Verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
except Exception:
    for name, backup in backups.items():
        objects[name].data = backup
    for mesh in new_meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    raise
else:
    for backup in backups.values():
        # Retain an unlinked recovery datablock, without changing live objects.
        backup.use_fake_user = True
        backup.name = 'Before angular S relief '+backup.name
print(json.dumps(report))
