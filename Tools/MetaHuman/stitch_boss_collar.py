"""Weld only the 46 paired Boss collar vertices in an export-only Blender scene.

Keep per-corner UVs/materials and fitted rig; blend paired skin weights and
positions, and carry the shared collar normals through the topological weld.
Never saves the source .blend.
"""
from collections import defaultdict
import bmesh
from mathutils import Vector
from boss_collar_normals import repair_collar_normals


def stitch_collar(obj):
    mesh=obj.data
    assert mesh.shape_keys is None, 'Shape keys require explicit synchronized welding'
    before_vertices=len(mesh.vertices)
    before_faces=len(mesh.polygons)
    repair=repair_collar_normals(obj)
    pairs=repair['boundary_pair_indices']
    merge_count=sum(a!=b for a,b in pairs)
    normals=[n.vector.copy() for n in mesh.corner_normals]
    old_uv=[[(d.uv.x,d.uv.y) for d in layer.data] for layer in mesh.uv_layers]
    old_materials=[p.material_index for p in mesh.polygons]
    positions=[v.co.copy() for v in mesh.vertices]
    bm=bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table();bm.faces.ensure_lookup_table()
    orig_loop=bm.loops.layers.int.new('boss_stitch_source_loop')
    orig_face=bm.faces.layers.int.new('boss_stitch_source_face')
    orig_vertex=bm.verts.layers.int.new('boss_stitch_source_vertex')
    for v in bm.verts:v[orig_vertex]=v.index
    for f in bm.faces:
        f[orig_face]=f.index
        for loop,li in zip(f.loops,mesh.polygons[f.index].loop_indices):loop[orig_loop]=li
    deform=bm.verts.layers.deform.verify()
    mapping={}
    max_weight_l1=0.
    for a,b in pairs:
        va,vb=bm.verts[a],bm.verts[b]
        point=(va.co+vb.co)*.5
        wa,wb=dict(va[deform]),dict(vb[deform])
        merged={g:(wa.get(g,0.)+wb.get(g,0.))*.5 for g in set(wa)|set(wb)}
        total=sum(merged.values());assert total>0
        merged={g:w/total for g,w in merged.items() if w>0}
        max_weight_l1=max(max_weight_l1,sum(abs(wa.get(g,0)-wb.get(g,0)) for g in merged))
        for v in (va,vb):
            v.co=point
            v[deform].clear()
            for g,w in merged.items():v[deform][g]=w
        if a!=b:
            mapping[vb]=va
    bmesh.ops.weld_verts(bm,targetmap=mapping)
    seam=[e for e in bm.edges if {f.material_index for f in e.link_faces}=={6,7}]
    assert len(seam)==46 and all(len(e.link_faces)==2 for e in seam), (len(seam),len(bm.verts),len(bm.faces),{m:sum(f.material_index==m for f in bm.faces) for m in (6,7)})
    for e in seam:e.smooth=True
    bm.to_mesh(mesh);bm.free();mesh.update()
    li_map=[d.value for d in mesh.attributes['boss_stitch_source_loop'].data]
    fi_map=[d.value for d in mesh.attributes['boss_stitch_source_face'].data]
    vi_map=[d.value for d in mesh.attributes['boss_stitch_source_vertex'].data]
    assert len(mesh.vertices)==before_vertices-merge_count and len(mesh.polygons)==before_faces
    assert sorted(li_map)==list(range(len(normals))), 'Weld unexpectedly changed face corners'
    for i,layer in enumerate(mesh.uv_layers):
        assert all((d.uv.x,d.uv.y)==old_uv[i][li_map[j]] for j,d in enumerate(layer.data))
    assert all(p.material_index==old_materials[fi_map[p.index]] for p in mesh.polygons)
    mesh.normals_split_custom_set([normals[i] for i in li_map]);mesh.update()
    by_old={old:new for new,old in enumerate(vi_map)}
    seam_vertices={by_old[a] for a,b in pairs}
    loops=defaultdict(list)
    for loop in mesh.loops:loops[loop.vertex_index].append(loop.index)
    actual=[n.vector.copy() for n in mesh.corner_normals]
    max_angle=max(actual[ls[0]].angle(actual[i]) for v in seam_vertices for ls in [loops[v]] for i in ls)
    assert max_angle<.001, ('Seam split normals differ',max_angle)
    unchanged=max((mesh.vertices[new].co-positions[old]).length for new,old in enumerate(vi_map) if new not in seam_vertices)
    assert unchanged==0
    for key in ('boss_stitch_source_loop','boss_stitch_source_face','boss_stitch_source_vertex'):
        mesh.attributes.remove(mesh.attributes[key])
    return {'collar_pairs':46,'welded_pairs':merge_count,'already_shared_pairs':46-merge_count,'vertices_before':before_vertices,'vertices_after':len(mesh.vertices),
            'faces_unchanged':before_faces,'shared_manifold_collar_edges':len(seam),
            'max_pre_stitch_gap_mm':repair['max_boundary_distance_mm'],
            'max_vertex_move_mm':repair['max_boundary_distance_mm']*.5,
            'outside_collar_position_delta_m':unchanged,'corner_uvs_and_materials_unchanged':True,
            'max_shared_normal_angle_degrees':max_angle*180/3.141592653589793,
            'weights':'Paired normalized average on each shared vertex; identical for both material sections',
            'max_original_pair_weight_l1_difference':max_weight_l1,
            'smooth_normal_band':repair,'collar_world_m':[list(obj.matrix_world@mesh.vertices[v].co) for v in sorted(seam_vertices)]}
