import bpy,json
art=bpy.data.collections['SPEAR • editable components']
print(json.dumps([{'name':o.name,'vertices':len(o.data.vertices),'z':[min(v.co.z for v in o.data.vertices),max(v.co.z for v in o.data.vertices)],'r':max((v.co.x**2+v.co.y**2)**.5 for v in o.data.vertices)} for o in art.objects if o.type=='MESH' and min(v.co.z for v in o.data.vertices)>1.59 and max(v.co.z for v in o.data.vertices)<1.81],indent=2))
