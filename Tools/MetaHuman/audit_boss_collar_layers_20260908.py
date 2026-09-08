"""Read-only source collar topology/overlap audit; never save the .blend."""
import json
from collections import Counter, defaultdict
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

OUT = Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/BossSeamAudit/20260908/collar_layers.json')
obj = bpy.data.objects['boss']
mesh = obj.data
world = [obj.matrix_world @ v.co for v in mesh.vertices]
edge_faces = defaultdict(list)
for p in mesh.polygons:
    for e in p.edge_keys:
        edge_faces[tuple(sorted(e))].append(p.index)

def center(p):
    return sum((world[v] for v in p.vertices), Vector()) / len(p.vertices)

def bounds(points):
    return [[min(p[d] for p in points) for d in range(3)], [max(p[d] for p in points) for d in range(3)]] if points else None

def collar(p):
    c = center(p)
    return 1.05 < c.z < 1.52 and abs(c.x) < 0.38

near_polys = [p for p in mesh.polygons if collar(p)]
materials = Counter(p.material_index for p in near_polys)
nonmanifold = []
mixed = []
for edge, faces in edge_faces.items():
    points = [world[v] for v in edge]
    c = (points[0]+points[1])*0.5
    if not (1.05 < c.z < 1.52 and abs(c.x) < 0.38):
        continue
    row = {'edge': edge, 'position_m': list(c), 'faces': faces, 'materials': [mesh.polygons[i].material_index for i in faces]}
    if len(faces) != 2:
        nonmanifold.append(row)
    if len(set(row['materials'])) > 1:
        mixed.append(row)

by_material = {m:[p for p in mesh.polygons if p.material_index==m] for m in (6,7)}
trees = {m:BVHTree.FromPolygons(world, [tuple(p.vertices) for p in ps], all_triangles=False) for m,ps in by_material.items()}
overlap = []
for p in near_polys:
    if p.material_index not in (6,7):
        continue
    other = 13-p.material_index
    nearest,normal,index,dist = trees[other].find_nearest(center(p))
    if dist < 0.001:
        q = by_material[other][index]
        n = (world[p.vertices[1]]-world[p.vertices[0]]).cross(world[p.vertices[2]]-world[p.vertices[0]]).normalized()
        overlap.append({'face':p.index,'material':p.material_index,'nearest_other_face':q.index,'distance_mm':dist*1000,'normal_dot':n.dot(normal),'centroid_m':list(center(p)),'shared_vertices':list(set(p.vertices)&set(q.vertices))})

# Independent ray intersections: from frontal/back view, collect one hit per
# material layer. Equal depth at many interior positions implies layered skin.
rays=[]
for ix in range(-14,15):
    for iz in range(105,153):
        x,z=ix*0.015,iz*0.01
        hits=[]
        for m,tree in trees.items():
            hit,n,index,dist=tree.ray_cast(Vector((x,-0.5,z)),Vector((0,1,0)),1.0)
            if hit is not None:
                hits.append({'mat':m,'y':hit.y,'face':by_material[m][index].index})
        if len(hits)==2 and abs(hits[0]['y']-hits[1]['y'])<0.02:
            rays.append({'x':x,'z':z,'separation_mm':abs(hits[0]['y']-hits[1]['y'])*1000,'hits':hits})

material_bounds={m:bounds([world[v] for p in ps for v in p.vertices]) for m,ps in by_material.items()}
boundary_sets={m:{v for edge,faces in edge_faces.items() if len(faces)==1 and mesh.polygons[faces[0]].material_index==m for v in edge} for m in(6,7)}
tree=KDTree(len(boundary_sets[7]))
for v in boundary_sets[7]:tree.insert(world[v],v)
tree.balance()
boundary_pairs=[]
normal_matrix=obj.matrix_world.to_3x3().inverted().transposed()
for v in boundary_sets[6]:
    p,b,d=tree.find(world[v]);n=(normal_matrix@mesh.vertices[v].normal).normalized();nb=(normal_matrix@mesh.vertices[b].normal).normalized()
    boundary_pairs.append({'face_vertex':v,'body_vertex':b,'distance_mm':d*1000,'normal_angle_deg':n.angle(nb)*57.2957795,'position_m':list(world[v])})
all_skin_mixed=[{'edge':edge,'position_m':list(sum((world[v] for v in edge),Vector())*0.5),'faces':faces,'materials':[mesh.polygons[i].material_index for i in faces]} for edge,faces in edge_faces.items() if set(mesh.polygons[i].material_index for i in faces)=={6,7}]
ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());em=ev.to_mesh();evaluated_counts={'vertices':len(em.vertices),'edges':len(em.edges),'faces':len(em.polygons)};ev.to_mesh_clear()
report={'source':bpy.data.filepath,'mesh':obj.name,'modifiers':[(m.name,m.type,m.show_viewport,m.show_render)for m in obj.modifiers],'evaluated_counts':evaluated_counts,'boundary_pairs':boundary_pairs,'material_bounds_m':material_bounds,'all_skin_mixed_edges':all_skin_mixed,'collar_material_face_count':dict(materials), 'collar_bounds_m':bounds([world[v] for p in near_polys for v in p.vertices]), 'nonmanifold_edges':nonmanifold,'mixed_material_edges':mixed,'near_overlapping_centroids_under_1mm':overlap,'front_rays_two_skin_material_hits_under_2cm':rays}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,indent=2))
print(json.dumps({'path':str(OUT),'materials':dict(materials),'nonmanifold':len(nonmanifold),'mixed':len(mixed),'near_overlaps':len(overlap),'rays':len(rays),'ray_gap_under_1mm':sum(r['separation_mm']<1 for r in rays)}))
