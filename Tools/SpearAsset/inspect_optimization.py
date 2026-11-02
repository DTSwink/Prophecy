import bpy,json,hashlib
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
OUT=ROOT/'Saved/Diagnostics/ImperialSpear/Optimization20261028'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s
art=bpy.data.collections['SPEAR • editable components']
items=[]
for o in art.objects:
 if o.type!='MESH':continue
 m=o.data;m.calc_loop_triangles()
 items.append(dict(name=o.name,verts=len(m.vertices),tris=len(m.loop_triangles),faces=len(m.polygons),custom_normals=m.has_custom_normals,uv=[x.name for x in m.uv_layers],colors=[x.name for x in m.color_attributes],modifiers=[x.name for x in o.modifiers],matrix=[list(r) for r in o.matrix_world],dimensions=list(o.dimensions)))
result={'path':bpy.data.filepath,'scene':s.name,'meshes':items,'triangles':sum(x['tris'] for x in items),'materials':[m.name for m in bpy.data.materials],'images':[(i.name,i.filepath) for i in bpy.data.images if i.source=='FILE'],'camera':s.camera.name if s.camera else None}
(OUT/'Initial_Inspection.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
