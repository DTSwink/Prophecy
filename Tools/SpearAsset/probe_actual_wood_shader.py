import bpy,json
art=bpy.data.collections['SPEAR • editable components']
ob=next(o for o in art.objects if o.name.startswith('01 •'))
report={'object':ob.name,'materials':[],'active_uv':ob.data.uv_layers.active.name,'render_uv':[u.name for u in ob.data.uv_layers if u.active_render]}
for mat in ob.data.materials:
    report['materials'].append({'name':mat.name,'nodes':[{'name':n.name,'image':n.image.name if n.type=='TEX_IMAGE' and n.image else None,'path':n.image.filepath if n.type=='TEX_IMAGE' and n.image else None} for n in mat.node_tree.nodes],
        'links':[[l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name] for l in mat.node_tree.links]})
print(json.dumps(report))
