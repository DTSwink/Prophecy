"""Read-only background FBX normal/tangent roundtrip audit; never save Blender."""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
from io_scene_fbx import parse_fbx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Saved/BossShading/20260908'
FBX = ROOT / 'Saved/BossUEFNCompatible/20260907/SKM_Boss_UEFN_Fitted.fbx'
SOURCE = Path(r'C:/Users/singerie/Documents/Blender/bossfinalsave.blend')


def unit(v):
    v = np.asarray(v, dtype=float)
    length = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(length, 1e-30)


def angle(a, b):
    return math.degrees(math.acos(float(np.clip(np.dot(a, b), -1, 1))))


def summary(values):
    a = np.asarray(values, dtype=float)
    return {'count': len(values), 'mean': float(a.mean()) if len(a) else None,
            'p99': float(np.percentile(a, 99)) if len(a) else None,
            'max': float(a.max()) if len(a) else None}


def capture(obj):
    bpy.context.view_layer.update()
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get())
    mesh.calc_tangents(uvmap=mesh.uv_layers.active.name)
    mat = np.asarray(ev.matrix_world, dtype=float)
    positions = np.asarray([list(v.co) for v in mesh.vertices], dtype=float)
    world = positions @ mat[:3, :3].T + mat[:3, 3]
    normals = np.asarray([list(n.vector) for n in mesh.corner_normals], dtype=float)
    tangents = np.asarray([list(loop.tangent) for loop in mesh.loops], dtype=float)
    result = {'positions': world, 'loop_vertices': [l.vertex_index for l in mesh.loops],
              'uv': np.asarray([list(uv.uv) for uv in mesh.uv_layers.active.data], dtype=float),
              'normal': unit(normals @ np.linalg.inv(mat[:3, :3])),
              'tangent': unit(tangents @ mat[:3, :3].T),
              'sign': np.asarray([l.bitangent_sign for l in mesh.loops], dtype=float),
              'polygons': [list(p.loop_indices) for p in mesh.polygons],
              'world_matrix': mat.tolist(), 'custom_normals': mesh.has_custom_normals}
    ev.to_mesh_clear()
    return result


def child(node, name):
    return next((e for e in node.elems if e.id == name), None)


def prop(node, name):
    c = child(node, name)
    return c.props[0] if c else None


def fbx_layer(geo, layer_name, value_name, width, vertices):
    layer = child(geo, layer_name)
    if layer is None:
        return None, None
    raw = np.asarray(prop(layer, value_name), dtype=float).reshape(-1, width)
    mapping, reference = prop(layer, b'MappingInformationType'), prop(layer, b'ReferenceInformationType')
    if mapping == b'ByPolygonVertex':
        indices = np.arange(len(vertices))
    elif mapping in (b'ByVertice', b'ByVertex', b'ByControlPoint'):
        indices = np.asarray(vertices)
    elif mapping == b'AllSame':
        indices = np.zeros(len(vertices), dtype=int)
    else:
        raise ValueError(('Unsupported mapping', layer_name, mapping))
    if reference == b'IndexToDirect':
        index_node = child(layer, value_name + b'Index') or child(layer, value_name[:-1] + b'Index')
        assert index_node is not None, (layer_name, [e.id for e in layer.elems])
        indices = np.asarray(index_node.props[0], dtype=int)[indices]
    else:
        assert reference == b'Direct', reference
    return raw[indices], {'mapping': mapping.decode(), 'reference': reference.decode(), 'values': len(raw)}


def seam_report(data):
    by_vertex = defaultdict(list)
    for li, vi in enumerate(data['loop_vertices']):
        by_vertex[vi].append(li)
    samples = []
    for vi, loops in by_vertex.items():
        representatives = {}
        for li in loops:
            key = tuple(round(float(v), 6) for v in data['uv'][li])
            representatives.setdefault(key, li)
        ids = list(representatives.values())
        if len(ids) < 2:
            continue
        error = max(angle(data['normal'][a], data['normal'][b]) for a in ids for b in ids)
        samples.append({'vertex': vi, 'position_m': data['positions'][vi].tolist(),
                        'uv_branches': len(ids), 'normal_angle_deg': error})
    return {'normal_angle_deg': summary([s['normal_angle_deg'] for s in samples]),
            'worst': sorted(samples, key=lambda s:s['normal_angle_deg'], reverse=True)[:20]}


def compare(source, target):
    kd = KDTree(len(source['positions']))
    for vi, p in enumerate(source['positions']):
        kd.insert(Vector(p), vi)
    kd.balance()
    source_loops = defaultdict(list)
    for li, vi in enumerate(source['loop_vertices']):
        source_loops[vi].append(li)
    pos_err, normals, tangents, sign_mismatch, missing, worst = [], [], [], 0, [], []
    binormals, body_normals, body_tangents = [], [], []
    vertex_matches = {}
    for vi, p in enumerate(target['positions']):
        near = kd.find_range(Vector(p), 1e-5)
        vertex_matches[vi] = [n[1] for n in near]
        pos_err.append(kd.find(Vector(p))[2])
    for ti, vi in enumerate(target['loop_vertices']):
        candidates = [li for si in vertex_matches[vi] for li in source_loops[si]
                      if np.max(np.abs(source['uv'][li] - target['uv'][ti])) < 1e-5]
        if not candidates:
            missing.append(ti)
            continue
        best = min(candidates, key=lambda si:angle(source['normal'][si], target['normal'][ti]) +
                   angle(source['tangent'][si], target['tangent'][ti]))
        ne = angle(source['normal'][best], target['normal'][ti])
        te = angle(source['tangent'][best], target['tangent'][ti])
        normals.append(ne)
        tangents.append(te)
        sign_mismatch += int(source['sign'][best] != target['sign'][ti])
        sb = np.cross(source['normal'][best],source['tangent'][best])*source['sign'][best]
        tb = np.cross(target['normal'][ti],target['tangent'][ti])*target['sign'][ti]
        binormals.append(angle(unit(sb), unit(tb)))
        if target['positions'][vi][2] < 1.4:
            body_normals.append(ne)
            body_tangents.append(te)
        if ne > 0.1 or te > 0.1:
            worst.append({'target_loop': ti, 'source_loop': best, 'normal_angle_deg': ne,
                          'tangent_angle_deg': te, 'position_m': target['positions'][vi].tolist(),
                          'uv': target['uv'][ti].tolist()})
    return {'position_error_m': summary(pos_err), 'normal_angle_deg': summary(normals),
            'tangent_angle_deg': summary(tangents), 'bitangent_sign_mismatches': sign_mismatch,
            'bitangent_angle_deg': summary(binormals),
            'below_1_4m_normal_angle_deg': summary(body_normals),
            'below_1_4m_tangent_angle_deg': summary(body_tangents),
            'unmatched_corners': len(missing), 'unmatched_examples': missing[:10],
            'worst': sorted(worst, key=lambda s:max(s['normal_angle_deg'],s['tangent_angle_deg']), reverse=True)[:25]}


def main():
    assert bpy.app.background and Path(bpy.data.filepath).resolve() == SOURCE.resolve()
    source = capture(bpy.data.objects['boss'])
    tree, version = parse_fbx.parse(str(FBX))
    objects = child(tree, b'Objects')
    geometry = next(e for e in objects.elems if e.id == b'Geometry' and e.props[-1] == b'Mesh')
    raw_vertices = np.asarray(prop(geometry, b'Vertices'), dtype=float).reshape(-1, 3)
    pvi = np.asarray(prop(geometry, b'PolygonVertexIndex'), dtype=int)
    loop_vertices = np.where(pvi < 0, -pvi-1, pvi).tolist()
    rn, normal_meta = fbx_layer(geometry, b'LayerElementNormal', b'Normals', 3, loop_vertices)
    rt, tangent_meta = fbx_layer(geometry, b'LayerElementTangent', b'Tangents', 3, loop_vertices)
    rb, binormal_meta = fbx_layer(geometry, b'LayerElementBinormal', b'Binormals', 3, loop_vertices)
    uv, uv_meta = fbx_layer(geometry, b'LayerElementUV', b'UV', 2, loop_vertices)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(FBX), use_custom_normals=True, use_anim=False,
                             automatic_bone_orientation=False, ignore_leaf_bones=False)
    mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
    imported = capture(mesh)
    # FBX import retains control point order; derive its coordinate mapping and validate it.
    assert len(raw_vertices) == len(imported['positions'])
    affine, *_ = np.linalg.lstsq(np.column_stack([raw_vertices, np.ones(len(raw_vertices))]), imported['positions'], rcond=None)
    fitted = np.column_stack([raw_vertices, np.ones(len(raw_vertices))]) @ affine
    affine_error = float(np.max(np.linalg.norm(fitted-imported['positions'], axis=1)))
    assert affine_error < 1e-5, affine_error
    linear = affine[:3].T
    raw = {'positions': imported['positions'], 'loop_vertices': loop_vertices, 'uv': uv,
           'normal': unit(rn @ np.linalg.inv(linear)), 'tangent': unit(rt @ linear.T),
           'sign': np.ones(len(loop_vertices))}
    raw_bitangent = unit(rb @ linear.T)
    raw['sign'] = np.sign(np.einsum('ij,ij->i',np.cross(raw['normal'],raw['tangent']),raw_bitangent))
    result = {'source': str(SOURCE), 'fbx': str(FBX), 'source_saved': False, 'fbx_version': version,
              'vertex_counts': [len(source['positions']),len(imported['positions'])],
              'corner_counts': [len(source['uv']),len(imported['uv']),len(uv)],
              'source_world_matrix': source['world_matrix'], 'imported_world_matrix': imported['world_matrix'],
              'source_custom_normals': source['custom_normals'], 'imported_custom_normals': imported['custom_normals'],
              'fbx_layers': {'normal': normal_meta,'tangent':tangent_meta,'binormal':binormal_meta,'uv':uv_meta},
              'fbx_to_imported_affine': affine.tolist(), 'fbx_to_imported_affine_max_error_m': affine_error,
              'source_vs_imported_blender': compare(source, imported),
              'source_vs_raw_fbx_basis': compare(source, raw),
              'source_uv_seams': seam_report(source), 'raw_fbx_uv_seams': seam_report(raw)}
    ue_path = OUT/'unreal_before.json'
    if ue_path.exists():
        ue = json.loads(ue_path.read_text())
        ue_corners = ue['corners']
        ue_normals = unit([c[2] for c in ue_corners])
        ue_tangents = unit([c[3] for c in ue_corners])
        ue_bitangents = unit([c[4] for c in ue_corners])
        ue_data = {'positions': np.asarray(ue['positions'],dtype=float)/100.0,
                   'loop_vertices': [c[0] for c in ue_corners],
                   'uv': np.asarray([c[1] for c in ue_corners],dtype=float),
                   'normal': ue_normals, 'tangent': ue_tangents,
                   'sign': np.sign(np.einsum('ij,ij->i',np.cross(ue_normals,ue_tangents),ue_bitangents))}
        reflect = np.asarray([1,-1,1],dtype=float)
        expected = dict(raw)
        expected['positions'] = raw['positions']*reflect
        expected['normal'] = raw['normal']*reflect
        expected['tangent'] = raw['tangent']*reflect
        expected['uv'] = raw['uv']*np.asarray([1,-1])+np.asarray([0,1])
        # Coordinate reflection and V reflection each negate handedness, cancelling.
        result['raw_fbx_vs_unreal_imported_basis'] = compare(expected,ue_data)
        result['unreal_uv_seams'] = seam_report(ue_data)
        result['unreal_count'] = {'vertices':len(ue_data['positions']),'corners':len(ue_corners)}
        # Standalone compact numerical artifact for further read-only comparisons.
        np.savez_compressed(OUT/'raw_fbx_basis_ue_coordinates.npz',positions=expected['positions'],
                            loop_vertices=expected['loop_vertices'],uv=expected['uv'],
                            normal=expected['normal'],tangent=expected['tangent'],sign=expected['sign'])
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'fbx_shading.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print('FBX_SHADING_AUDIT', json.dumps({k:v for k,v in result.items() if k not in ('source_uv_seams','raw_fbx_uv_seams')},indent=2))


def compare_saved_ue(label):
    """Fast follow-up for a separately captured Unreal source or render mesh."""
    expected = dict(np.load(OUT/'raw_fbx_basis_ue_coordinates.npz'))
    ue = json.loads((OUT/(label+'.json')).read_text())
    corners = ue['corners']
    normals, tangents, bitangents = (unit([c[i] for c in corners]) for i in (2,3,4))
    actual = {'positions':np.asarray(ue['positions'],dtype=float)/100.0,
              'loop_vertices':[c[0] for c in corners], 'uv':np.asarray([c[1] for c in corners]),
              'normal':normals,'tangent':tangents,
              'sign':np.sign(np.einsum('ij,ij->i',np.cross(normals,tangents),bitangents))}
    result = {'label':label, 'vertices':len(actual['positions']), 'corners':len(corners),
              'comparison':compare(expected,actual), 'uv_seams':seam_report(actual)}
    (OUT/(label+'_comparison.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
    print('UE_RENDER_BASIS_AUDIT',json.dumps({**result,'uv_seams':result['uv_seams']['normal_angle_deg']},indent=2))


def audit_connectivity():
    data = dict(np.load(OUT/'raw_fbx_basis_ue_coordinates.npz'))
    points = data['positions']
    triangles = data['loop_vertices'].reshape(-1,3)
    nverts = len(points)
    parent = list(range(nverts))
    edges = defaultdict(list)
    neighbors = defaultdict(set)
    vertex_loops = defaultdict(list)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for ti, tri in enumerate(triangles):
        for corner, a in enumerate(tri):
            a, b = int(a),int(tri[(corner+1)%3])
            aa,bb = find(a),find(b)
            parent[aa] = bb
            edges[tuple(sorted((a,b)))].append(ti)
            neighbors[a].add(b)
            neighbors[b].add(a)
            vertex_loops[a].append(ti*3+corner)
    groups = defaultdict(list)
    for vi in range(nverts):
        groups[find(vi)].append(vi)
    sorted_groups = sorted(groups.values(),key=len,reverse=True)
    component = {vi:ci for ci,vs in enumerate(sorted_groups) for vi in vs}
    boundary_edges = [edge for edge,ts in edges.items() if len(ts)==1]
    boundary_vertices = sorted({v for edge in boundary_edges for v in edge})
    nonmanifold = [edge for edge,ts in edges.items() if len(ts)>2]
    tree, _ = parse_fbx.parse(str(FBX))
    geo = next(e for e in child(tree,b'Objects').elems if e.id==b'Geometry' and e.props[-1]==b'Mesh')
    material_layer = child(geo,b'LayerElementMaterial')
    materials = list(prop(material_layer,b'Materials'))
    if len(materials)==1:
        materials *= len(triangles)
    assert len(materials)==len(triangles)
    comp_rows = []
    for ci,vs in enumerate(sorted_groups):
        pp = points[vs]
        mats = sorted({materials[li//3] for v in vs for li in vertex_loops[v]})
        comp_rows.append({'component':ci,'vertices':len(vs),'bbox_cm':[(pp.min(axis=0)*100).tolist(),(pp.max(axis=0)*100).tolist()],
                          'material_indices':mats, 'boundary_edges':sum(component[a]==ci for a,b in boundary_edges)})

    def pair_audit(vertices, only_boundary):
        kd=KDTree(len(vertices))
        for vi in vertices:
            kd.insert(Vector(points[vi]),vi)
        kd.balance()
        pairs=[]
        for a in vertices:
            for _,b,d in kd.find_range(Vector(points[a]),0.01):
                if b<=a or b in neighbors[a]:
                    continue
                na=data['normal'][vertex_loops[a][0]]
                nb=data['normal'][vertex_loops[b][0]]
                dist_cm=d*100
                pairs.append({'a':a,'b':b,'distance_cm':dist_cm,'normal_angle_deg':angle(na,nb),
                              'components':[component[a],component[b]],
                              'positions_cm':[(points[a]*100).tolist(),(points[b]*100).tolist()],
                              'materials':[sorted({materials[li//3] for li in vertex_loops[a]}),
                                           sorted({materials[li//3] for li in vertex_loops[b]})]})
        thresholds={}
        for threshold in (0.001,0.01,0.1,1.0):
            subset=[p for p in pairs if p['distance_cm']<=threshold]
            cross=[p for p in subset if p['components'][0]!=p['components'][1]]
            thresholds[str(threshold)]={'pair_count':len(subset),'different_component_pairs':len(cross),
                                        'normal_angle_deg':summary([p['normal_angle_deg'] for p in subset]),
                                        'worst':sorted(subset,key=lambda p:p['normal_angle_deg'],reverse=True)[:20]}
        return {'boundary_vertices_only':only_boundary,'thresholds_cm':thresholds}

    material_borders=[]
    for (a,b),ts in edges.items():
        if len(ts)!=2 or materials[ts[0]]==materials[ts[1]]:
            continue
        endpoint_errors=[]
        for vi in (a,b):
            li0=ts[0]*3+list(triangles[ts[0]]).index(vi)
            li1=ts[1]*3+list(triangles[ts[1]]).index(vi)
            endpoint_errors.append(angle(data['normal'][li0],data['normal'][li1]))
        material_borders.append({'edge':[a,b],'materials':[materials[t] for t in ts],
                                 'max_normal_angle_deg':max(endpoint_errors),
                                 'midpoint_cm':((points[a]+points[b])*50).tolist()})
    result={'vertices':nverts,'triangles':len(triangles),'edges':len(edges),'components':comp_rows,
            'boundary_edge_count':len(boundary_edges),'boundary_vertex_count':len(boundary_vertices),
            'nonmanifold_edge_count':len(nonmanifold),
            'nonmanifold_edges':[{'edge':[a,b],'triangles':edges[(a,b)],
                                  'materials':[materials[ti] for ti in edges[(a,b)]],
                                  'positions_cm':[(points[a]*100).tolist(),(points[b]*100).tolist()]}
                                 for a,b in nonmanifold],
            'main_component_boundary_edges':[{'edge':[a,b],'materials':[materials[ti] for ti in edges[(a,b)]],
                                               'positions_cm':[(points[a]*100).tolist(),(points[b]*100).tolist()]}
                                              for a,b in boundary_edges if component[a]==0],
            'material_border_edges':{'count':len(material_borders),
                                    'normal_angle_deg':summary([p['max_normal_angle_deg'] for p in material_borders]),
                                    'edges':material_borders},
            'boundary_pairs':pair_audit(boundary_vertices,True),
            'all_unconnected_vertex_pairs':pair_audit(list(range(nverts)),False)}
    (OUT/'geometry_connectivity.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print('GEOMETRY_CONNECTIVITY',json.dumps({k:v for k,v in result.items() if k not in ('boundary_pairs','all_unconnected_vertex_pairs','material_border_edges')},indent=2))


def audit_candidate():
    candidate=ROOT/'Saved/BossUEFNCompatible/20260908_Shading/SKM_Boss_UEFN_Fitted.fbx'
    old,_=parse_fbx.parse(str(FBX))
    new,_=parse_fbx.parse(str(candidate))
    oo,nn=child(old,b'Objects'),child(new,b'Objects')
    og=next(e for e in oo.elems if e.id==b'Geometry' and e.props[-1]==b'Mesh')
    ng=next(e for e in nn.elems if e.id==b'Geometry' and e.props[-1]==b'Mesh')

    def plain(v):
        if isinstance(v,bytes):
            return v.decode('utf8',errors='backslashreplace')
        if hasattr(v,'tolist'):
            return v.tolist()
        if isinstance(v,(list,tuple)):
            return [plain(x) for x in v]
        return v

    def payload(e,skip_id=False):
        return [plain(e.id),plain(e.props[1:] if skip_id else e.props),[payload(c)for c in e.elems]]

    def object_payload(objects,kind):
        return sorted(json.dumps(payload(e,True),sort_keys=True) for e in objects.elems if e.id==kind)

    def bind_matrices(objects):
        identifiers={e.props[0]:plain(e.id)+':'+str(plain(e.props[1:]))for e in objects.elems if e.props}
        result={}
        for pose in (e for e in objects.elems if e.id==b'Pose'):
            for node in (e for e in pose.elems if e.id==b'PoseNode'):
                result[identifiers[prop(node,b'Node')]]=plain(prop(node,b'Matrix'))
        return result

    controls=np.asarray(prop(og,b'Vertices')).reshape(-1,3)
    newcontrols=np.asarray(prop(ng,b'Vertices')).reshape(-1,3)
    polygon_indices=np.asarray(prop(og,b'PolygonVertexIndex'))
    new_polygon_indices=np.asarray(prop(ng,b'PolygonVertexIndex'))
    vertices=np.where(polygon_indices<0,-polygon_indices-1,polygon_indices).tolist()
    oldn,_=fbx_layer(og,b'LayerElementNormal',b'Normals',3,vertices)
    newn,_=fbx_layer(ng,b'LayerElementNormal',b'Normals',3,vertices)
    oldt,_=fbx_layer(og,b'LayerElementTangent',b'Tangents',3,vertices)
    newt,_=fbx_layer(ng,b'LayerElementTangent',b'Tangents',3,vertices)
    olduv,_=fbx_layer(og,b'LayerElementUV',b'UV',2,vertices)
    newuv,_=fbx_layer(ng,b'LayerElementUV',b'UV',2,vertices)
    counts=defaultdict(list)
    for li,vi in enumerate(vertices):
        counts[vi].append(li)
    oldvn={vi:unit(oldn[ids].mean(axis=0))for vi,ids in counts.items()}
    newvn={vi:unit(newn[ids].mean(axis=0))for vi,ids in counts.items()}
    pairs=json.loads((candidate.parent/'export_audit.json').read_text())['collar_shading_repair']['boundary_pair_indices']
    pair_before=[angle(oldvn[a],oldvn[b])for a,b in pairs]
    pair_after=[angle(newvn[a],newvn[b])for a,b in pairs]
    normal_changes=np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i',unit(oldn),unit(newn)),-1,1)))
    tangent_changes=np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i',unit(oldt),unit(newt)),-1,1)))
    ignore={b'LayerElementNormal',b'LayerElementTangent',b'LayerElementBinormal',b'Layer'}
    othergeo_old={plain(e.id):payload(e)for e in og.elems if e.id not in ignore}
    othergeo_new={plain(e.id):payload(e)for e in ng.elems if e.id not in ignore}
    changed_othergeo=[k for k in othergeo_old.keys()|othergeo_new.keys() if othergeo_old.get(k)!=othergeo_new.get(k)]
    oldbind,newbind=bind_matrices(oo),bind_matrices(nn)
    checks={'control_positions_exact':np.array_equal(controls,newcontrols),
            'polygon_indices_exact':np.array_equal(polygon_indices,new_polygon_indices),
            'uv_corners_exact':np.array_equal(olduv,newuv),
            'all_model_properties_exact':object_payload(oo,b'Model')==object_payload(nn,b'Model'),
            'all_deformer_cluster_properties_exact':object_payload(oo,b'Deformer')==object_payload(nn,b'Deformer'),
            'all_bind_pose_matrices_exact':oldbind==newbind,
            'other_geometry_attributes_exact':not changed_othergeo}
    report={'before':str(FBX),'candidate':str(candidate),'checks':checks,
            'control_point_max_difference_raw_units':float(np.max(np.abs(controls-newcontrols))),
            'bind_pose_node_counts':[len(oldbind),len(newbind)],
            'bind_pose_max_matrix_difference':max(float(np.max(np.abs(np.asarray(m)-newbind[k])))for k,m in oldbind.items())if oldbind.keys()==newbind.keys()else None,
            'other_geometry_attribute_changes':changed_othergeo,
            'normal_corner_change_degrees':summary(normal_changes.tolist()),
            'tangent_corner_change_degrees':summary(tangent_changes.tolist()),
            'normal_changed_vertices_over_0_01deg':len({vertices[i]for i,v in enumerate(normal_changes)if v>0.01}),
            'collar_pairs':len(pairs),'collar_normal_angle_before_deg':summary(pair_before),
            'collar_normal_angle_after_deg':summary(pair_after),
            'collar_geometry_gap_unchanged':bool(np.array_equal(controls,newcontrols)),
            'passed':all(checks.values())}
    (OUT/'candidate_fbx_validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('CANDIDATE_FBX_VALIDATION',json.dumps(report,indent=2))


def audit_body_normalmap():
    data=dict(np.load(OUT/'raw_fbx_basis_ue_coordinates.npz'))
    points=data['positions']
    indices=data['loop_vertices']
    uv=data['uv']
    tri_uv=uv.reshape(-1,3,2).mean(axis=1)
    tree,_=parse_fbx.parse(str(FBX))
    geo=next(e for e in child(tree,b'Objects').elems if e.id==b'Geometry' and e.props[-1]==b'Mesh')
    materials=np.asarray(prop(child(geo,b'LayerElementMaterial'),b'Materials'))
    image=bpy.data.images.load(str(OUT/'T_Body_N.png'),check_existing=False)
    image.colorspace_settings.name='Non-Color'
    w,h=image.size
    pixels=np.empty(w*h*4,dtype=np.float32)
    image.pixels.foreach_get(pixels)
    # Blender pixels start at bottom-left; Unreal UVs and exported PNG rows at top-left.
    pixels=pixels.reshape(h,w,4)[::-1,:,:3]

    def bilinear(tuv):
        xy=(tuv%1.0)*np.asarray([w,h])-0.5
        xy0=np.floor(xy).astype(int)
        f=xy-xy0
        x0,y0=xy0[0]%w,xy0[1]%h
        x1,y1=(x0+1)%w,(y0+1)%h
        return pixels[y0,x0]*(1-f[0])*(1-f[1])+pixels[y0,x1]*f[0]*(1-f[1])+pixels[y1,x0]*(1-f[0])*f[1]+pixels[y1,x1]*f[0]*f[1]

    body_loops=defaultdict(lambda:defaultdict(list))
    for li,vi in enumerate(indices):
        if materials[li//3]!=0:
            continue
        key=tuple(round(float(v),6)for v in uv[li])+(float(data['sign'][li]),)
        body_loops[int(vi)][key].append(li)
    export=json.loads((ROOT/'Saved/BossUEFNCompatible/20260907/export_audit.json').read_text())
    hands=[np.asarray([export['converted_rest_world_cm'][name][i][3]for i in range(3)])*np.asarray([1,-1,1])/100 for name in ('hand_l','hand_r')]
    reports={}
    for green in (1,-1):
        for inset in (0.0,0.25,1.0):
            pairs=[]
            for vi,groups in body_loops.items():
                if len(groups)<2 or points[vi][2]>1.28:
                    continue
                charts=[]
                for key,lis in groups.items():
                    normals=[]
                    rgbs=[]
                    for li in lis:
                        sample_uv=uv[li].copy()
                        if inset:
                            direction=tri_uv[li//3]-sample_uv
                            scale=np.linalg.norm(direction*np.asarray([w,h]))
                            if scale>1e-9:
                                sample_uv+=direction*min(inset/scale,1.0)
                        rgb=bilinear(sample_uv)
                        x,y=(rgb[:2]*2-1)*np.asarray([1,green])
                        z=math.sqrt(max(0.0,1-x*x-y*y))
                        tn=unit([x,y,z])
                        n=data['normal'][li]
                        t=data['tangent'][li]
                        b=np.cross(n,t)*data['sign'][li]
                        normals.append(unit(t*tn[0]+b*tn[1]+n*tn[2]))
                        rgbs.append(rgb)
                    charts.append({'uv':list(key[:2]),'normal':unit(np.mean(normals,axis=0)),
                                   'rgb':np.mean(rgbs,axis=0).tolist()})
                for ia,a in enumerate(charts):
                    for b in charts[ia+1:]:
                        position_cm=(points[vi]*100).tolist()
                        region='other_body'
                        if min(np.linalg.norm(points[vi]-hand)for hand in hands)<0.10:
                            region='wrist_hand_10cm'
                        elif abs(points[vi][0])<0.22 and 0.95<points[vi][2]<1.18:
                            region='waist_belly'
                        pairs.append({'vertex':vi,'position_cm':position_cm,'region':region,
                                      'normal_angle_deg':angle(a['normal'],b['normal']),
                                      'uv_a':a['uv'],'uv_b':b['uv'],'rgb_a':a['rgb'],'rgb_b':b['rgb']})
            key=f'green_{green:+d}_inset_{inset:g}_px'
            reports[key]={'pair_count':len(pairs),'normal_angle_deg':summary([p['normal_angle_deg']for p in pairs]),
                          'regions':{region:{'normal_angle_deg':summary([p['normal_angle_deg']for p in pairs if p['region']==region]),
                                             'worst':sorted([p for p in pairs if p['region']==region],key=lambda p:p['normal_angle_deg'],reverse=True)[:12]}
                                     for region in ('waist_belly','wrist_hand_10cm','other_body')}}
    result={'texture':str(OUT/'T_Body_N.png'),'dimensions':[w,h],
            'pixel_rgb_min':pixels.min(axis=(0,1)).tolist(),'pixel_rgb_max':pixels.max(axis=(0,1)).tolist(),
            'pixel_rgb_mean':pixels.mean(axis=(0,1)).tolist(),
            'method':'Repeat-wrap bilinear sample at chart-boundary UVs, BC5 XY decoded and positive Z reconstructed; chart normals averaged across incident triangles; excludes collar/head above128cm; micro detail omitted.',
            'reports':reports}
    (OUT/'body_normalmap_seams.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print('BODY_NORMALMAP_SEAMS',json.dumps({k:{'all':v['normal_angle_deg'],**{r:a['normal_angle_deg']for r,a in v['regions'].items()}}for k,v in reports.items()},indent=2))


if __name__ == '__main__':
    if '--compare-ue' in sys.argv:
        compare_saved_ue(sys.argv[sys.argv.index('--compare-ue')+1])
    elif '--connectivity' in sys.argv:
        audit_connectivity()
    elif '--candidate' in sys.argv:
        audit_candidate()
    elif '--body-normalmap' in sys.argv:
        audit_body_normalmap()
    else:
        main()
