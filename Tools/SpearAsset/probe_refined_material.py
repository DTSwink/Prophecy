import bpy,json
art=bpy.data.collections['SPEAR • editable components']
m=next(o for o in art.objects if o.type=='MESH').data.materials[0]
print(json.dumps({'mat':m.name,'images':[{'node':n.name,'name':n.image.name,'path':n.image.filepath,'color_space':n.image.colorspace_settings.name} for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]}))
