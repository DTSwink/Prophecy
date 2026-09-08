"""Offline Boss collar-normal repair; no vertex, UV, skin-weight or rig edits.

Call repair_collar_normals(mesh_object) before the fitted FBX export. Source
material indices default to body7/face6 (before material-region remapping).
The equal-size closed rings are matched bijectively by cyclic topology, not
independent nearest-neighbor queries. Unequal topology is rejected deliberately.
"""
import json
import math
from collections import defaultdict, deque
from pathlib import Path
import bpy
from mathutils import Vector, Quaternion


def _unit_average(values):
    values = list(values)
    value = sum(values, Vector())
    if value.length < 1e-10:
        raise RuntimeError('Degenerate collar normal average')
    return value.normalized()


def _angle(a, b):
    return math.degrees(a.angle(b))


def _ring(edges):
    adjacency = defaultdict(list)
    for a,b in edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
    if len(adjacency)!=46 or any(len(v)!=2 for v in adjacency.values()):
        raise RuntimeError('Expected one simple 46-vertex Boss collar ring')
    start=min(adjacency)
    ring=[start]
    previous=None
    current=start
    while True:
        following=next(n for n in sorted(adjacency[current]) if n!=previous)
        if following==start:
            break
        if following in ring:
            raise RuntimeError('Collar boundary has multiple or branching loops')
        ring.append(following)
        previous,current=current,following
    if len(ring)!=len(adjacency):
        raise RuntimeError('Collar ring did not visit every boundary vertex')
    return ring


def repair_collar_normals(obj, body_material=7, face_material=6, interior_rings=2):
    mesh=obj.data
    if interior_rings not in (0,1,2):
        raise ValueError('Use zero, one or two interior rings only')
    coordinates=[v.co.copy() for v in mesh.vertices]
    weights_before=[tuple((g.group,g.weight)for g in v.groups)for v in mesh.vertices]
    uv_before=[[(float(d.uv.x),float(d.uv.y))for d in layer.data]for layer in mesh.uv_layers]
    corners_before=[n.vector.copy() for n in mesh.corner_normals]
    edge_faces=defaultdict(list)
    vertex_loops=defaultdict(list)
    material_neighbors={m:defaultdict(set) for m in (body_material,face_material)}
    for polygon in mesh.polygons:
        for li in polygon.loop_indices:
            vertex_loops[mesh.loops[li].vertex_index].append(li)
        for edge in polygon.edge_keys:
            edge=tuple(sorted(edge))
            edge_faces[edge].append(polygon.index)
            if polygon.material_index in material_neighbors:
                a,b=edge
                material_neighbors[polygon.material_index][a].add(b)
                material_neighbors[polygon.material_index][b].add(a)
    rings={m:_ring([edge for edge,fs in edge_faces.items() if len(fs)==1 and mesh.polygons[fs[0]].material_index==m]) for m in material_neighbors}
    world=[obj.matrix_world@v.co for v in mesh.vertices]
    body=rings[body_material]
    face=rings[face_material]
    candidates=[]
    for reverse in (False,True):
        oriented=list(reversed(face)) if reverse else face
        for offset in range(len(face)):
            matched=oriented[offset:]+oriented[:offset]
            score=sum((world[a]-world[b]).length_squared for a,b in zip(body,matched))
            candidates.append((score,reverse,offset,matched))
    score,reverse,offset,face=min(candidates,key=lambda x:x[0])
    pairs=list(zip(body,face))
    if max((world[a]-world[b]).length for a,b in pairs)>.008:
        raise RuntimeError('Collar rings are more than 8mm apart; needs artist decision')
    original={v:_unit_average(corners_before[li] for li in vertex_loops[v]) for pair in pairs for v in pair}
    correction={}
    target={}
    for a,b in pairs:
        shared=_unit_average((original[a],original[b]))
        for v in (a,b):
            target[v]=shared
            correction[v]=original[v].rotation_difference(shared)
    # Propagate only the small ROTATION needed at the collar. Keeping local
    # curvature avoids flattening the first interior ring toward the border.
    propagated={m:defaultdict(list) for m in material_neighbors}
    for material,ring in rings.items():
        adjacency=material_neighbors[material]
        boundary=set(ring)
        for seed in ring:
            queue=deque([(seed,0)])
            seen={seed}
            while queue:
                vertex,d=queue.popleft()
                if vertex not in boundary:
                    propagated[material][vertex].append((seed,d))
                if d==interior_rings:
                    continue
                for neighbor in adjacency[vertex]:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        queue.append((neighbor,d+1))
    corners_after=[n.copy() for n in corners_before]
    altered_vertices=set(target)
    influence_rings=defaultdict(set)
    for v,normal in target.items():
        for li in vertex_loops[v]:
            corners_after[li]=normal.copy()
        influence_rings[0].add(v)
    for material,vertices in propagated.items():
        for v,contributors in vertices.items():
            min_ring=min(d for _,d in contributors)
            nearest=[seed for seed,d in contributors if d==min_ring]
            t=min_ring/(interior_rings+1.0)
            strength=1.0-t*t*(3.0-2.0*t)
            rotations=[Quaternion().slerp(correction[seed],strength) for seed in nearest]
            for li in vertex_loops[v]:
                corners_after[li]=_unit_average(rotation@corners_before[li] for rotation in rotations)
            altered_vertices.add(v)
            influence_rings[min_ring].add(v)
    mesh.normals_split_custom_set(corners_after)
    mesh.update()
    actual=[n.vector.copy() for n in mesh.corner_normals]
    after_normal={v:_unit_average(actual[li] for li in vertex_loops[v]) for pair in pairs for v in pair}
    before_angles=[_angle(original[a],original[b]) for a,b in pairs]
    after_angles=[_angle(after_normal[a],after_normal[b]) for a,b in pairs]
    unchanged=[_angle(actual[i],corners_before[i]) for i,loop in enumerate(mesh.loops) if loop.vertex_index not in altered_vertices]
    changes=[_angle(actual[i],corners_before[i]) for i,loop in enumerate(mesh.loops) if loop.vertex_index in altered_vertices]
    if any((v.co-coordinates[v.index]).length>0 for v in mesh.vertices):
        raise RuntimeError('Unexpected geometry change')
    if weights_before!=[tuple((g.group,g.weight)for g in v.groups)for v in mesh.vertices]:
        raise RuntimeError('Unexpected skin weight change')
    if uv_before!=[[(float(d.uv.x),float(d.uv.y))for d in layer.data]for layer in mesh.uv_layers]:
        raise RuntimeError('Unexpected UV change')
    return {'pairs':len(pairs),'topology_matching_reversed':reverse,'topology_matching_offset':offset,
        'max_boundary_distance_mm':max((world[a]-world[b]).length for a,b in pairs)*1000,
        'max_normal_angle_before_deg':max(before_angles),'mean_normal_angle_before_deg':sum(before_angles)/len(pairs),
        'max_normal_angle_after_deg':max(after_angles),'mean_normal_angle_after_deg':sum(after_angles)/len(pairs),
        'max_changed_corner_angle_deg':max(changes),'outside_band_max_corner_change_deg':max(unchanged),
        'altered_vertices':len(altered_vertices),'interior_ring_count':interior_rings,
        'vertices_per_ring':{d:len(vs)for d,vs in influence_rings.items()},'geometry_delta_m':0.0,
        'weight_data_unchanged':True,'uv_data_unchanged':True,
        'altered_band_bounds_m':[[min(world[v][d]for v in altered_vertices)for d in range(3)],[max(world[v][d]for v in altered_vertices)for d in range(3)]],
        'shared_boundary_vertices':len(set(body)&set(face)),
        'boundary_pair_indices':pairs}


if __name__=='__main__':
    # Read-only background test. Only transient normal attributes are changed;
    # no .blend save, no FBX export, and no Unreal asset import is performed.
    audit=repair_collar_normals(bpy.data.objects['boss'])
    out=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/BossSeamAudit/20260908/collar_normals_candidate.json')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(audit,indent=2))
    print('BOSS_COLLAR_NORMALS '+json.dumps({k:v for k,v in audit.items() if k!='boundary_pair_indices'}))
