import bpy,json
o=bpy.data.objects['02 • carved lotus pommel body'];m=o.data;m.calc_loop_triangles();bad=[]
for tri in m.loop_triangles:
 for i in tri.loops:
  dot=m.corner_normals[i].vector.dot(tri.normal)
  if dot<.3:bad.append({'dot':dot,'polygon':tri.polygon_index,'corner':i,'co':list(m.vertices[m.loops[i].vertex_index].co),'normal':list(m.corner_normals[i].vector),'face':list(tri.normal)})
print(json.dumps({'count':len(bad),'examples':sorted(bad,key=lambda x:x['dot'])[:18]},indent=2))
