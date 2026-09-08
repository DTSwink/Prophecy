"""Read-only background Blender shading/topology probe; never save source."""
import json
import math
from collections import defaultdict, Counter
from pathlib import Path
import bpy
from mathutils import Vector

assert bpy.app.background
obj=bpy.data.objects['boss']
m=obj.data
loops=defaultdict(list)
for p in m.polygons:
    for li in p.loop_indices:
        loops[m.loops[li].vertex_index].append((li,p.index))
normals=[n.vector.copy() for n in m.corner_normals]
worst=[]
for vi,ls in loops.items():
    angle=max((normals[a].angle(normals[b],0.) for a,_ in ls for b,_ in ls),default=0.)
    if angle>math.radians(5):
        worst.append({'vertex':vi,'position':list(obj.matrix_world@m.vertices[vi].co),
            'angle_degrees':math.degrees(angle),'materials':list({m.polygons[pi].material_index for _,pi in ls})})
bypos=defaultdict(list)
for v in m.vertices: bypos[tuple(round(float(x),5) for x in v.co)].append(v.index)
report={'source':bpy.data.filepath,'vertices':len(m.vertices),'faces':len(m.polygons),
    'has_custom_normals':m.has_custom_normals,'attributes':[(a.name,a.domain,a.data_type) for a in m.attributes],
    'flat_faces':sum(not p.use_smooth for p in m.polygons),'sharp_edges':sum(e.use_edge_sharp for e in m.edges),
    'material_faces':dict(Counter(p.material_index for p in m.polygons)),
    'material_names':[s.name for s in m.materials],
    'modifiers':[(mod.name,mod.type) for mod in obj.modifiers],
    'split_normal_vertices':len(worst),'worst_splits':sorted(worst,key=lambda r:-r['angle_degrees'])[:80],
    'coincident_groups':[v for v in bypos.values() if len(v)>1]}
out=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/BossShading/20260908')
out.mkdir(parents=True,exist_ok=True)
(out/'source_shading.json').write_text(json.dumps(report,indent=2))
print('BOSS_SHADING',json.dumps({k:v for k,v in report.items() if k not in ('worst_splits','coincident_groups')}))
print('COINCIDENT_GROUPS',len(report['coincident_groups']))
print('WORST_SPLITS',report['worst_splits'][:10])
