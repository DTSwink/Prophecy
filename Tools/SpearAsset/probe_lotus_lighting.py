import bpy,json
s=bpy.data.scenes['Scene'];m=bpy.data.materials['M_ImperialSpear_PommelGold']
def nodes(nt):
 return [{'name':n.name,'type':n.type,'image':n.image.filepath if n.type=='TEX_IMAGE' and n.image else None,
          'inputs':{i.name:list(i.default_value) if hasattr(i.default_value,'__len__') else i.default_value for i in n.inputs if hasattr(i,'default_value') and isinstance(i.default_value,(float,int,tuple))}} for n in nt.nodes]
print(json.dumps({'world':nodes(s.world.node_tree),'world_links':[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in s.world.node_tree.links],
 'lights':[(o.name,o.data.type,o.data.energy,list(o.location)) for o in s.objects if o.type=='LIGHT'],'material':nodes(m.node_tree),
 'material_links':[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in m.node_tree.links]},default=str,indent=2))
