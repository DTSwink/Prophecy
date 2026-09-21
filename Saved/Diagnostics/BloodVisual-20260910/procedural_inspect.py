import unreal,builtins
s=builtins._blood_visual;p=s['actors']['ProceduralStains'];c=p.mesh_component
print('MESH_MATERIAL',c.get_material(0),'STAIN_MATERIAL',p.stain_material)
m=p.stain_material
print('GRAPH',unreal.MaterialEditingLibrary.get_material_property_input_node(m,unreal.MaterialProperty.MP_EMISSIVE_COLOR),'SHADING',m.get_editor_property('shading_model'))
print('SECTION',unreal.ProceduralMeshLibrary.get_section_from_procedural_mesh(c,0))
