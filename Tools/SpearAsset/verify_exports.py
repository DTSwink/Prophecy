"""Verify FBX against the current GAME scene; always remove temporary readback.

Verifies authored/exported geometry and the source texture contract. Unreal
import, collision cooking, physics and FBX shader wiring remain unvalidated.
"""
import bpy
import bmesh
import json
import math
import re
import struct
import hashlib
from pathlib import Path
from mathutils import kdtree,Vector

ROOT = Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
OUT = ROOT / 'Exports/ImperialSpear'
POSITION_TOLERANCE_M = 1e-5
UV_TOLERANCE = 1e-5
MINIMUM_NORMAL_DOT = .9999
CONVEX_TOLERANCE_M = 1e-6
MAX_HULL_VERTICES = 64
UV_NAMES = ['UV0_SurfaceAtlas', 'UV1_Lightmap']
CAVITY_COLOR = 'PommelCavity'
COLOR_TOLERANCE = 3.1e-5  # Covers glTF normalized uint16 colors; FBX remains float.


def material_name(material):
    assert material is not None, 'Empty material slot'
    return re.sub(r'\.\d{3,}$', '', material.name)


def material_assignment_counts(ob):
    result={material_name(m):0 for m in ob.data.materials}
    for polygon in ob.data.polygons:
        result[material_name(ob.data.materials[polygon.material_index])]+=len(polygon.vertices)-2
    return result


def world_vertices(ob):
    coords = [ob.matrix_world @ vertex.co for vertex in ob.data.vertices]
    assert coords and all(math.isfinite(c) for point in coords for c in point), ob.name
    return coords


def bounds(coords):
    return {'min': [min(p[i] for p in coords) for i in range(3)],
            'max': [max(p[i] for p in coords) for i in range(3)]}


def point_cloud_error(first, second):
    """Bidirectional positions allow legitimate UV/normal-seam duplication."""
    def directed(source, target):
        tree = kdtree.KDTree(len(target))
        for index, point in enumerate(target):
            tree.insert(point, index)
        tree.balance()
        return max(tree.find(point)[2] for point in source)
    return max(directed(first, second), directed(second, first))


def surface_records(ob):
    """Read world-space shading at each corner, including hard-edge/UV seams."""
    uv = ob.data.uv_layers['UV0_SurfaceAtlas']
    normal_matrix = ob.matrix_world.to_3x3().inverted().transposed()
    normals = ob.data.corner_normals
    assert len(normals) == len(uv.data) == len(ob.data.loops), ob.name
    coords = world_vertices(ob)
    color=ob.data.color_attributes.get(CAVITY_COLOR)
    if color:
        assert color.domain=='CORNER' and color.data_type=='FLOAT_COLOR',(ob.name,'Expected linear float corner colors')
        colors=[tuple(item.color) for item in color.data]
    else:colors=[(1.,1.,1.,1.)]*len(ob.data.loops)
    assert len(colors)==len(ob.data.loops)
    assert all(all(math.isfinite(c) for c in shade) for shade in colors)
    records, by_vertex = [], [[] for _ in coords]
    corner_materials = [None]*len(ob.data.loops)
    for polygon in ob.data.polygons:
        assigned = material_name(ob.data.materials[polygon.material_index])
        for index in polygon.loop_indices:corner_materials[index]=assigned
    for index, loop in enumerate(ob.data.loops):
        normal = normal_matrix @ normals[index].vector
        texcoord = tuple(uv.data[index].uv)
        assert all(math.isfinite(c) for c in (*texcoord, *normal)), (ob.name, index)
        assert normal.length > .5, ('Invalid shading normal', ob.name, index)
        normal.normalize()
        records.append((coords[loop.vertex_index], texcoord, normal, corner_materials[index], colors[index]))
        by_vertex[loop.vertex_index].append(index)
    assert records, ('No render corners', ob.name)
    return records, coords, by_vertex


def surface_record_error(source_data, imported_data, format_name='FBX'):
    """Match actual UV0 and normals both ways; corner order may change in FBX.

    Quantized positions/UVs make normal cases cheap. A radius query resolves
    quantization boundaries and coincident corners with different seam normals.
    Multiplicity may legitimately change at seams; every corner must have a
    compatible corner in the other mesh, and triangle totals are checked too.
    """
    def key(record):
        position, uv, _, assigned, _ = record
        return (assigned,)+tuple(round(c/POSITION_TOLERANCE_M) for c in position) + tuple(round(c/UV_TOLERANCE) for c in uv)

    def directed(first, second, label):
        candidates, coords, by_vertex = second
        buckets = {}
        for index, record in enumerate(candidates):
            buckets.setdefault(key(record), []).append(index)
        tree = kdtree.KDTree(len(coords))
        for index, point in enumerate(coords):
            tree.insert(point, index)
        tree.balance()
        worst_position, worst_uv, worst_color, minimum_dot, fallbacks = 0.0, 0.0, 0.0, 1.0, 0
        for index, record in enumerate(first[0]):
            position, uv, normal, assigned, shade = record

            def best(indices):
                matches = []
                for candidate_index in indices:
                    other_position, other_uv, other_normal, other_material, other_shade = candidates[candidate_index]
                    if assigned != other_material:continue
                    position_error = (position-other_position).length
                    uv_error = max(abs(uv[i]-other_uv[i]) for i in range(2))
                    color_error = max(abs(shade[i]-other_shade[i]) for i in range(4))
                    if position_error <= POSITION_TOLERANCE_M and uv_error <= UV_TOLERANCE and color_error<=COLOR_TOLERANCE:
                        matches.append((normal.dot(other_normal), position_error, uv_error, color_error))
                return max(matches, key=lambda item: (item[0], -item[1], -item[2], -item[3])) if matches else None

            match = best(buckets.get(key(record), ()))
            if match is None or match[0] < MINIMUM_NORMAL_DOT:
                fallbacks += 1
                nearby = tree.find_range(position, POSITION_TOLERANCE_M*1.00001)
                match = best(corner for _, vertex_index, _ in nearby for corner in by_vertex[vertex_index])
            assert match is not None, (format_name+' position/UV0/color/material corner mismatch', label, index, list(position), uv, shade)
            assert match[0] >= MINIMUM_NORMAL_DOT, (format_name+' shading-normal mismatch', label, index, match[0], list(position), uv)
            minimum_dot = min(minimum_dot, match[0])
            worst_position, worst_uv = max(worst_position, match[1]), max(worst_uv, match[2])
            worst_color=max(worst_color,match[3])
        return {'corners_checked': len(first[0]), 'maximum_position_error_m': worst_position,
                'maximum_uv0_error': worst_uv, 'minimum_normal_dot': minimum_dot,
                'maximum_linear_color_error':worst_color,
                'kdtree_fallbacks': fallbacks, 'material_assignment_checked_per_corner': True,
                'linear_vertex_color_checked_per_corner':True}

    forward = directed(source_data, imported_data, 'source to '+format_name)
    reverse = directed(imported_data, source_data, format_name+' to source')
    label=format_name.lower()
    return {'source_to_'+label: forward, label+'_to_source': reverse,
            'position_tolerance_m': POSITION_TOLERANCE_M, 'uv0_tolerance': UV_TOLERANCE,
            'required_minimum_normal_dot': MINIMUM_NORMAL_DOT,
            'maximum_uv0_error': max(forward['maximum_uv0_error'], reverse['maximum_uv0_error']),
            'linear_color_tolerance':COLOR_TOLERANCE,
            'maximum_linear_color_error':max(forward['maximum_linear_color_error'],reverse['maximum_linear_color_error']),
            'minimum_normal_dot': min(forward['minimum_normal_dot'], reverse['minimum_normal_dot'])}


def surface_readback_error(source, imported):
    return surface_record_error(surface_records(source),surface_records(imported),'FBX')


def verify_glb_cavity(render):
    """Read actual GLB COLOR_0, including uint16 normalization and UV convention."""
    payload=(OUT/'SM_ImperialSpear.glb').read_bytes()
    magic,version,total=struct.unpack_from('<4sII',payload,0)
    assert magic==b'glTF' and version==2 and total==len(payload),'Invalid GLB header'
    offset=12;document=None;binary=None
    while offset<len(payload):
        size,kind=struct.unpack_from('<II',payload,offset);offset+=8
        chunk=payload[offset:offset+size];offset+=size
        if kind==0x4e4f534a:document=json.loads(chunk)
        elif kind==0x004e4942:binary=chunk
    assert document is not None and binary is not None,'Missing GLB JSON/BIN'
    assert len(document['meshes'])==1 and len(document['meshes'][0]['primitives'])==1
    mesh_nodes=[n for n in document['nodes'] if 'mesh' in n]
    assert len(mesh_nodes)==1 and mesh_nodes[0]['mesh']==0
    assert not any(k in mesh_nodes[0] for k in ('matrix','translation','rotation','scale')),'Unexpected GLB render transform'
    primitive=document['meshes'][0]['primitives'][0];attributes=primitive['attributes']
    assert 'COLOR_0' in attributes and primitive.get('mode',4)==4,'Missing GLB cavity COLOR_0'
    formats={5121:('B',1,255.),5123:('H',2,65535.),5125:('I',4,4294967295.),5126:('f',4,1.)}
    widths={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}
    def read_accessor(index):
        accessor=document['accessors'][index]
        assert 'sparse' not in accessor and accessor['componentType'] in formats
        code,size,maximum=formats[accessor['componentType']];width=widths[accessor['type']]
        view=document['bufferViews'][accessor['bufferView']]
        assert view.get('buffer',0)==0
        start=view.get('byteOffset',0)+accessor.get('byteOffset',0)
        stride=view.get('byteStride',size*width)
        rows=[struct.unpack_from('<'+code*width,binary,start+i*stride) for i in range(accessor['count'])]
        if accessor.get('normalized'):rows=[tuple(float(v)/maximum for v in row) for row in rows]
        return rows
    positions=read_accessor(attributes['POSITION']);normals=read_accessor(attributes['NORMAL'])
    uvs=read_accessor(attributes['TEXCOORD_0']);colors=read_accessor(attributes['COLOR_0'])
    indices=[row[0] for row in read_accessor(primitive['indices'])]
    assert len(positions)==len(normals)==len(uvs)==len(colors)
    assert len(indices)==len(render.data.loops),'GLB triangle/corner count changed'
    coordinates=[Vector((x,-z,y)) for x,y,z in positions]
    by_vertex=[[] for _ in coordinates];records=[]
    assigned=material_name(render.data.materials[0])
    for corner,index in enumerate(indices):
        nx,ny,nz=normals[index];u,v=uvs[index];shade=tuple(colors[index])
        if len(shade)==3:shade+= (1.,)
        assert len(shade)==4 and all(math.isfinite(c) for c in shade)
        records.append((coordinates[index],(u,1-v),Vector((nx,-nz,ny)).normalized(),assigned,shade))
        by_vertex[index].append(corner)
    material=document['materials'][primitive['material']]
    pbr=material['pbrMetallicRoughness'];factor=pbr.get('baseColorFactor',[1,1,1,1])
    assert max(abs(c-1) for c in factor)<1e-6,('GLB applies an extra base-color factor',factor)
    image=document['images'][document['textures'][pbr['baseColorTexture']['index']]['source']]
    view=document['bufferViews'][image['bufferView']]
    encoded=binary[view.get('byteOffset',0):view.get('byteOffset',0)+view['byteLength']]
    authoritative=(OUT/'Textures/T_ImperialSpear_BaseColor.png').read_bytes()
    assert encoded==authoritative,'GLB base-color image differs from the unchanged authoritative atlas'
    return {'color_attribute':'COLOR_0','encoding':'linear neutral grayscale shade; alpha1',
        'component_type':document['accessors'][attributes['COLOR_0']]['componentType'],
        'normalized':document['accessors'][attributes['COLOR_0']].get('normalized',False),
        'base_color_factor':factor,'base_color_image_sha256':hashlib.sha256(encoded).hexdigest(),
        'base_color_image_matches_authoritative_atlas':True,'standard_vertex_color_multiply_count':1,
        'surface_attributes':surface_record_error(surface_records(render),(records,coordinates,by_vertex),'GLB')}


def canonical_name(actual, expected):
    if actual in expected:
        return actual
    # GAME objects stay loaded; import may append Blender's collision suffix.
    base = re.sub(r'\.\d{3,}$', '', actual)
    assert base in expected, ('Unexpected FBX object', actual, sorted(expected))
    return base


def indexed_objects(objects, expected):
    result = {}
    for ob in objects:
        name = canonical_name(ob.name, expected)
        assert name not in result, ('Duplicate FBX object', name)
        result[name] = ob
    assert set(result) == set(expected), ('FBX names differ', sorted(result), sorted(expected))
    return result


def hull_stats(ob):
    bm = bmesh.new()
    try:
        bm.from_mesh(ob.data)
        for vertex in bm.verts:
            vertex.co = ob.matrix_world @ vertex.co
        bm.normal_update()
        assert bm.faces and all(math.isfinite(c) for v in bm.verts for c in v.co), ob.name
        violation = 0.0
        for face in bm.faces:
            assert face.calc_area() > 1e-14, ('Degenerate collision face', ob.name)
            origin = face.verts[0].co
            violation = max(violation, max((v.co-origin).dot(face.normal) for v in bm.verts))
        result = {'vertices': len(bm.verts), 'triangles': sum(len(f.verts)-2 for f in bm.faces),
                  'boundary_edges': sum(e.is_boundary for e in bm.edges),
                  'nonmanifold_edges': sum(not e.is_manifold for e in bm.edges),
                  'volume_m3': bm.calc_volume(signed=True),
                  'convex_max_plane_violation_m': violation}
        assert 4 <= result['vertices'] <= MAX_HULL_VERTICES, (ob.name, result)
        assert result['boundary_edges'] == result['nonmanifold_edges'] == 0, (ob.name, result)
        assert result['volume_m3'] > 0, (ob.name, result)
        assert violation < CONVEX_TOLERANCE_M, (ob.name, result)
        return result
    finally:
        bm.free()


def source_texture_contract(render, version):
    contract = {'base_color': 'sRGB', 'normal': 'Non-Color; NormalDX for Unreal',
                'orm_channels': {'R': 'Ambient Occlusion', 'G': 'Roughness', 'B': 'Metallic'},
                'source_shader_verified': False, 'fbx_material_wiring_verified': False,
                'unreal_material_wiring_verified': False}
    if version < 2:
        return contract
    per_material=[]
    for material in render.data.materials:
        assert material.use_nodes and material.node_tree, 'Missing source PBR node tree'
        nodes, links = material.node_tree.nodes, material.node_tree.links
        orm=next((n for n in nodes if n.type=='TEX_IMAGE' and n.image and '_ORM' in n.image.name),None)
        principled=next((n for n in nodes if n.type=='BSDF_PRINCIPLED'),None)
        assert orm and orm.image and principled, ('Missing source ORM or Principled node',material.name)
        assert orm.image.colorspace_settings.name == 'Non-Color', 'ORM must be linear data'
        assert orm.image.alpha_mode == 'CHANNEL_PACKED', 'ORM alpha must not premultiply RGB'
        assert any(link.from_node == orm and link.from_socket.name == 'Alpha'
                   and link.to_node == principled and link.to_socket.name == 'Specular IOR Level'
                   for link in links), 'Source ORM alpha is not connected to specular level'
        assert not principled.inputs['Alpha'].is_linked, 'Packed ORM alpha must not control opacity'
        assert abs(principled.inputs['Alpha'].default_value-1.0) < 1e-6, 'Surface must remain opaque'
        if material.get('PommelCavityEnabled'):
            attribute=nodes.get('PommelCavity_Attribute')
            separate=nodes.get('PommelCavity_SeparateShade')
            gate=nodes.get('PommelCavity_PresenceGate')
            multiply=nodes.get('PommelCavity_BaseMultiply')
            original=nodes.get('PommelCavity_BaseOriginal')
            assert material.get('PommelCavityGate')=='COLOR_R_GT_0.01','Obsolete/unsafe cavity presence gate'
            assert attribute and attribute.type=='ATTRIBUTE' and attribute.attribute_name==CAVITY_COLOR
            assert separate and separate.type=='SEPARATE_COLOR' and separate.mode=='RGB'
            assert gate and gate.type=='MATH' and gate.operation=='GREATER_THAN' and abs(gate.inputs[1].default_value-.01)<1e-7
            assert not gate.inputs[1].is_linked,'Cavity presence threshold must remain fixed'
            assert multiply and multiply.blend_type=='MULTIPLY' and original
            def connected(output,input):
                return any(link.from_socket==output and link.to_socket==input for link in links)
            assert connected(attribute.outputs['Color'],separate.inputs[0])
            assert connected(separate.outputs[0],gate.inputs[0])
            assert connected(gate.outputs[0],multiply.inputs[0])
            assert connected(original.outputs[0],multiply.inputs[1])
            assert connected(attribute.outputs['Color'],multiply.inputs[2])
            assert connected(multiply.outputs[0],principled.inputs['Base Color'])
            assert not any(link.from_socket==attribute.outputs['Alpha'] and link.to_socket==multiply.inputs[0] for link in links),'Attribute alpha must not gate cavity presence'
        orm_path = Path(bpy.path.abspath(orm.image.filepath))
        with orm_path.open('rb') as stream:
            header = stream.read(33)
        assert header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR', orm_path
        assert header[25] == 6, ('ORM PNG must be RGBA', orm_path, header[25])
        per_material.append({'material':material.name,'source_orm_file':str(orm_path),
                             'source_shader_verified':True,'surface_opaque':True})
    contract.update({'orm_channels': {**contract['orm_channels'], 'A': 'Specular IOR Level'},
                     'orm_alpha_mode': 'CHANNEL_PACKED', 'source_orm_file': per_material[0]['source_orm_file'],
                     'materials':per_material,
                     'source_shader_verified': True, 'surface_opaque': True})
    return contract


def run_verification():
    original_scene = bpy.context.scene
    game = bpy.data.scenes['GAME • Unreal export']
    original_render = game.objects['SM_ImperialSpear']
    expected_hulls = {ob.name: ob for ob in game.objects if ob.type == 'MESH' and ob.name.startswith('UCX_')}
    expected_sockets = {ob.name: ob for ob in game.objects if ob.name.startswith('SOCKET_')}
    assert expected_hulls, 'No source collision hulls to verify'
    assert len(expected_sockets) == 4, ('Expected four attachment markers', sorted(expected_sockets))
    for owner in (game, original_render):
        declared = owner.get('CollisionHullCount')
        if declared is not None:
            assert int(declared) == len(expected_hulls), ('Stale collision-count metadata', owner.name)
    version = int(original_render.get('CollisionVersion', game.get('CollisionVersion',
                  bpy.data.scenes['Scene'].get('GoldDetailCollisionVersion', 0))))
    grip = float(original_render.get('Grip_reference_m', 1.235))
    source_coords = world_vertices(original_render)
    source_bounds = bounds(source_coords)
    length=source_bounds['max'][2]-source_bounds['min'][2]
    assert abs(float(original_render.get('Length_m',length))-length)<POSITION_TOLERANCE_M,'Stale length metadata'
    expected_materials={material_name(m) for m in original_render.data.materials}
    lotus=original_render.get('PommelDesign')=='lotus_bud'
    cavity_enabled=bool(original_render.get('PommelCavityEnabled',False))
    if cavity_enabled:assert original_render.data.color_attributes.get(CAVITY_COLOR) is not None,'Missing GAME cavity colors'
    assert expected_materials=={'M_ImperialSpear_PBR'},expected_materials
    assert [layer.name for layer in original_render.data.uv_layers] == UV_NAMES
    assert len(original_render.data.materials) == len(expected_materials)
    texture_contract = source_texture_contract(original_render, version)
    # Remove only new, unused datablocks created by this isolated readback.
    before_ids = {kind: set(getattr(bpy.data, kind)) for kind in ('meshes', 'materials', 'images')}
    test = bpy.data.scenes.new('TEMP • FBX readback')
    report = None
    try:
        bpy.context.window.scene = test
        bpy.ops.import_scene.fbx(filepath=str(OUT/'SM_ImperialSpear.fbx'), use_custom_normals=True,colors_type='LINEAR')
        meshes = [ob for ob in test.objects if ob.type == 'MESH' and not ob.name.startswith('UCX_')]
        hulls = [ob for ob in test.objects if ob.name.startswith('UCX_')]
        sockets = [ob for ob in test.objects if ob.name.startswith('SOCKET_')]
        assert len(meshes) == 1 and len(hulls) == len(expected_hulls) and len(sockets) == 4, (
            len(meshes), len(hulls), len(sockets), len(expected_hulls))
        imported_hulls = indexed_objects(hulls, expected_hulls)
        imported_sockets = indexed_objects(sockets, expected_sockets)
        ob = meshes[0]
        coords = world_vertices(ob)
        actual_bounds = bounds(coords)
        assert abs(actual_bounds['max'][2]-actual_bounds['min'][2]-length) < POSITION_TOLERANCE_M, actual_bounds
        bounds_error = max(abs(actual_bounds[side][axis]-source_bounds[side][axis])
                           for side in ('min', 'max') for axis in range(3))
        max_error = point_cloud_error(coords, source_coords)
        assert max_error < POSITION_TOLERANCE_M and bounds_error < POSITION_TOLERANCE_M, (max_error, bounds_error)
        assert [layer.name for layer in ob.data.uv_layers] == UV_NAMES, [layer.name for layer in ob.data.uv_layers]
        assert all(math.isfinite(c) for layer in ob.data.uv_layers for item in layer.data for c in item.uv)
        assert len(ob.data.materials)==len(expected_materials) and {material_name(m) for m in ob.data.materials}==expected_materials
        if cavity_enabled:assert ob.data.color_attributes.get(CAVITY_COLOR) is not None,'FBX dropped the cavity color layer'
        assert material_assignment_counts(ob)==material_assignment_counts(original_render),'FBX material triangle assignments changed'
        surface_report = surface_readback_error(original_render, ob)
        triangles = sum(len(poly.vertices)-2 for poly in ob.data.polygons)
        assert triangles == sum(len(poly.vertices)-2 for poly in original_render.data.polygons), 'Render triangle count changed'
        hull_reports = []
        for name, imported in sorted(imported_hulls.items()):
            source = expected_hulls[name]
            imported_points, source_points = world_vertices(imported), world_vertices(source)
            imported_bounds, expected_bounds = bounds(imported_points), bounds(source_points)
            error = point_cloud_error(imported_points, source_points)
            hull_bounds_error = max(abs(imported_bounds[side][axis]-expected_bounds[side][axis])
                                    for side in ('min', 'max') for axis in range(3))
            assert max(error, hull_bounds_error) < POSITION_TOLERANCE_M, (name, error, hull_bounds_error)
            source_stats, imported_stats = hull_stats(source), hull_stats(imported)
            hull_reports.append({'name': name, **imported_stats,
                                 'source_vertices': source_stats['vertices'], 'bounds_m': imported_bounds,
                                 'max_vertex_readback_error_m': error,
                                 'max_bounds_readback_error_m': hull_bounds_error})
        socket_report = {}
        for name, imported in sorted(imported_sockets.items()):
            position = imported.matrix_world.translation
            expected = expected_sockets[name].matrix_world.translation
            assert all(math.isfinite(c) for c in position)
            assert (position-expected).length < POSITION_TOLERANCE_M, (name, list(position), list(expected))
            socket_report[name] = [round(c, 7) for c in position]
        assert abs(socket_report['SOCKET_SM_ImperialSpear_BladeTip'][2]-(2.2-grip)) < POSITION_TOLERANCE_M
        assert max(abs(c) for c in socket_report['SOCKET_SM_ImperialSpear_Grip']) < POSITION_TOLERANCE_M
        assert abs(socket_report['SOCKET_SM_ImperialSpear_Pommel'][2]-source_bounds['min'][2])<POSITION_TOLERANCE_M
        lod_reports = []
        for number in (1, 2):
            name = 'SM_ImperialSpear_LOD%d' % number
            source_lod = game.objects.get(name)
            assert source_lod and source_lod.type == 'MESH', ('Missing source LOD', name)
            previous_objects = set(test.objects)
            bpy.ops.import_scene.fbx(filepath=str(OUT/(name+'.fbx')), use_custom_normals=True,colors_type='LINEAR')
            imported_objects = [item for item in test.objects if item not in previous_objects]
            assert len(imported_objects) == 1 and imported_objects[0].type == 'MESH', ('Unexpected LOD contents', name)
            lod = imported_objects[0]
            assert canonical_name(lod.name, {name}) == name
            assert [layer.name for layer in lod.data.uv_layers] == UV_NAMES, ('LOD UV layers changed', name)
            assert len(lod.data.materials)==len(expected_materials) and {material_name(m) for m in lod.data.materials}==expected_materials, ('LOD material count changed', name)
            if cavity_enabled:assert lod.data.color_attributes.get(CAVITY_COLOR) is not None,('LOD FBX dropped cavity colors',name)
            assert material_assignment_counts(lod)==material_assignment_counts(source_lod),('LOD material assignments changed',name)
            assert all(math.isfinite(c) for layer in lod.data.uv_layers for item in layer.data for c in item.uv), name
            lod_triangles = sum(len(poly.vertices)-2 for poly in lod.data.polygons)
            assert lod_triangles == sum(len(poly.vertices)-2 for poly in source_lod.data.polygons), ('LOD triangle count changed', name)
            assert 0 < lod_triangles < triangles, ('LOD does not reduce geometry', name)
            lod_coords, expected_coords = world_vertices(lod), world_vertices(source_lod)
            lod_bounds, expected_bounds = bounds(lod_coords), bounds(expected_coords)
            lod_error = point_cloud_error(lod_coords, expected_coords)
            lod_bounds_error = max(abs(lod_bounds[side][axis]-expected_bounds[side][axis])
                                   for side in ('min', 'max') for axis in range(3))
            assert max(lod_error, lod_bounds_error) < POSITION_TOLERANCE_M, (name, lod_error, lod_bounds_error)
            lod_reports.append({'name': name, 'triangles': lod_triangles, 'bounds_m': lod_bounds,
                                'max_vertex_readback_error_m': lod_error,
                                'max_bounds_readback_error_m': lod_bounds_error,
                                'surface_attributes': surface_readback_error(source_lod, lod),
                                'appearance_reviewed': False})
        report = {'fbx_meshes': len(meshes), 'fbx_hulls': len(hulls), 'fbx_sockets': len(sockets),
                  'collision_version': version, 'expected_hull_names': sorted(expected_hulls),
                  'bounds_m': actual_bounds, 'max_vertex_readback_error_m': max_error,
                  'max_bounds_readback_error_m': bounds_error,
                  'triangles': triangles, 'uv_channels': len(ob.data.uv_layers), 'uv_names': UV_NAMES,
                  'surface_attributes': surface_report,
                  'material_slots': len(ob.data.materials), 'material_triangles':material_assignment_counts(ob),
                  'overall_length_m':length,'grip_from_pommel_m':-source_bounds['min'][2], 'sockets': socket_report,
                  'lods': lod_reports,
                  'collision': hull_reports, 'texture_contract': texture_contract,
                  'cavity_vertex_color':{'enabled':cavity_enabled,'name':CAVITY_COLOR,'fbx_color_space':'LINEAR'},
                  'glb_cavity':verify_glb_cavity(original_render) if cavity_enabled else None,
                  'unreal_import_validated': False, 'unreal_collision_cooking_validated': False}
    finally:
        bpy.context.window.scene = original_scene
        for obj in list(test.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.scenes.remove(test)
        for kind in ('meshes', 'materials', 'images'):
            datablocks = getattr(bpy.data, kind)
            for block in list(datablocks):
                if block not in before_ids[kind] and block.users == 0:
                    datablocks.remove(block)
    # Publish success only after all assertions and cleanup have completed.
    (OUT/'Export_Verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


run_verification()
