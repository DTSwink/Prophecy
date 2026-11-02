import bpy,json,math
from pathlib import Path
out=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
ob=bpy.data.scenes['GAME • Unreal export'].objects['SM_ImperialSpear_LOD2'];mesh=ob.data
bad={i for i,n in enumerate(mesh.corner_normals) if n.vector.length<.5 or not all(math.isfinite(c) for c in n.vector)}
rows=[]
for p in mesh.polygons:
    if bad.intersection(p.loop_indices):
        rows.append({'polygon':p.index,'area':p.area,'normal':list(p.normal),'verts':[list(mesh.vertices[i].co) for i in p.vertices],
                     'corner_normals':[list(mesh.corner_normals[i].vector) for i in p.loop_indices]})
report={'bad_corners':len(bad),'bad_polygons':len(rows),'minimum_area':min(p.area for p in mesh.polygons),'details':rows}
(out/'LOD_Normal_Probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
