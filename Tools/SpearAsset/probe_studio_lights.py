import bpy,json
print(json.dumps([{'name':o.name,'type':o.data.type,'location':list(o.location),'energy':o.data.energy,'size':o.data.size if hasattr(o.data,'size') else None,'size_y':getattr(o.data,'size_y',None),'rotation':list(o.rotation_euler)} for o in bpy.data.scenes['Scene'].objects if o.type=='LIGHT']))
