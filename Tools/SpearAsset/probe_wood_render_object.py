import bpy,json
from mathutils import Vector
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;d=bpy.context.evaluated_depsgraph_get()
result=s.ray_cast(d,Vector((0,-3,1.42)),Vector((0,1,0)))
print('RAY',result[0],result[4].name if result[0] else None)
for o in s.objects:
 if o.type=='MESH':
  pts=[o.matrix_world@Vector(p) for p in o.bound_box]
  if min(v.z for v in pts)<=1.42<=max(v.z for v in pts) and min(v.x for v in pts)<=0<=max(v.x for v in pts):
   print('OVERLAP',o.name,'hide_render',o.hide_render,'visible_get',o.visible_get(),'collections',[(c.name,c.hide_render) for c in o.users_collection], 'bounds_y',min(v.y for v in pts),max(v.y for v in pts))
print('SCENECOLLECTIONS',[(c.name,c.hide_render) for c in s.collection.children])
