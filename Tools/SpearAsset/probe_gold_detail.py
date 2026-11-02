import bpy,json
from mathutils import Vector
art=bpy.data.collections['SPEAR • editable components']
names=('Blade • crown','Socket •','05 •','07 •')
rows=[]
for o in art.objects:
    if not o.name.startswith(names): continue
    c=[v.co for v in o.data.vertices]
    rows.append({'name':o.name,'vertices':len(c),'min':[min(v[i] for v in c) for i in range(3)],'max':[max(v[i] for v in c) for i in range(3)]})
print(json.dumps(rows,indent=2))
