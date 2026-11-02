import bpy,json,hashlib
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
WORK=ROOT/'Saved/Diagnostics/ImperialSpear/PommelLeaf'
art=bpy.data.collections['SPEAR • editable components']
def fingerprint(o):
    m=o.data
    data={'v':[list(v.co) for v in m.vertices],'f':[list(p.vertices) for p in m.polygons],
          'uv':{l.name:[list(v.uv) for v in l.data] for l in m.uv_layers},
          'normals':[list(n.vector) for n in m.corner_normals],
          'materials':[s.material.name if s.material else None for s in o.material_slots],
          'matrix':[list(r) for r in o.matrix_world]}
    return hashlib.sha256(json.dumps(data,separators=(',',':')).encode()).hexdigest()
report={o.name:{'fingerprint':fingerprint(o),'triangles':sum(len(p.vertices)-2 for p in o.data.polygons),
                'vertices':len(o.data.vertices),'bounds':[[min((o.matrix_world@v.co)[i] for v in o.data.vertices),max((o.matrix_world@v.co)[i] for v in o.data.vertices)] for i in range(3)]}
        for o in art.objects if o.type=='MESH'}
dest=WORK/'Baseline_Source_Components.json'
assert not dest.exists(),'Do not overwrite pre-edit baseline'
dest.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'mesh_count':len(report),'pommel':{k:v for k,v in report.items() if k.startswith(('02 •','Pommel •'))},
                  'wood':{k:v for k,v in report.items() if 'wood' in k.lower()},'active_scene':bpy.context.scene.name},indent=2))
