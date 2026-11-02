import bpy,json
m=bpy.data.materials['M_ImperialSpear_PBR']
for n in m.node_tree.nodes:
 if n.type in ('NORMAL_MAP','BSDF_PRINCIPLED'):
  print(n.name,{x.name: (list(x.default_value) if hasattr(x.default_value,'__len__') else x.default_value) for x in n.inputs if x.name in ('Strength','Normal','Roughness','Metallic','Specular IOR Level','Coat Weight','Coat Roughness','Specular Tint')})
print('Normaluv',m.node_tree.nodes['Normal Map'].uv_map)
