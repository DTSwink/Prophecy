"""Save audited concept04 V5 source/export for user review and close owned Blender."""
import bpy,json
from pathlib import Path
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');O=R/'Exports/ImperialSpear';W=R/'Saved/Diagnostics/ImperialSpear/PommelLotus'
source=bpy.data.scenes['Scene'];game=bpy.data.scenes['GAME • Unreal export']
audit=json.loads((O/'Pommel_Lotus_Verification.json').read_text(encoding='utf-8'))
verified=json.loads((O/'Export_Verification.json').read_text(encoding='utf-8'))
geometry=json.loads((W/'Geometry_Report.json').read_text(encoding='utf-8'))
cavity=json.loads((W/'Cavity_Material_Report.json').read_text(encoding='utf-8'))
protected_render=json.loads((W/'RefinementV4/Protected_Surface_Render_Check.json').read_text(encoding='utf-8'))
bud=next(c['design_report'] for c in geometry['components'] if c['name']=='Pommel • six carved lotus petals')
assert geometry['body_design']['main_body_lobes']==4 and geometry['body_design']['full_three_dimensional_section']
assert geometry['body_design']['secondary_carved_panels']==4 and geometry['body_design']['secondary_border_integral_geometry']
assert bud['design'].startswith('Lotus bud V5:')
assert geometry['body_design']['localized_cavity_mask']
assert audit['status']=='LOTUS_POMMEL_SOURCE_AND_ACTUAL_GAME_COLLISION_AUDITED'
assert verified['triangles']==audit['source_game_comparison']['source_triangles']==len(game.objects['SM_ImperialSpear'].data.polygons)
assert verified['fbx_hulls']==game['CollisionHullCount']==17
assert verified['material_slots']==1
assert [m.name for m in game.objects['SM_ImperialSpear'].data.materials]==['M_ImperialSpear_PBR']
assert geometry['triangles']==audit['source_game_comparison']['pommel_triangles']
assert verified['cavity_vertex_color']['enabled'] and verified['cavity_vertex_color']['fbx_color_space']=='LINEAR'
assert verified['glb_cavity']['standard_vertex_color_multiply_count']==1
assert cavity['material']=='M_ImperialSpear_PBR' and cavity['attribute']=='PommelCavity'
assert not cavity['original_textures_changed'] and not cavity['protected_source_color_layers_modified']
assert not cavity['roughness_metallic_normal_specular_changed']
assert cavity['source_presence_gate'].startswith('Color.R > 0.01;')
assert protected_render['status']=='PASS' and protected_render['maximum_channel_difference']<.001 and protected_render['mean_channel_difference']<1e-5,'Protected-head shader render comparison failed'
material=bpy.data.materials['M_ImperialSpear_PBR'];nodes=material.node_tree.nodes
assert material.get('PommelCavityEnabled') and material.get('PommelCavityRoughnessChanged') is False
assert material.get('PommelCavityGate')=='COLOR_R_GT_0.01'
attribute=nodes.get('PommelCavity_Attribute');multiply=nodes.get('PommelCavity_BaseMultiply');original=nodes.get('PommelCavity_BaseOriginal')
separate=nodes.get('PommelCavity_SeparateShade');gate=nodes.get('PommelCavity_PresenceGate')
principled=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
assert attribute and attribute.attribute_name=='PommelCavity' and attribute.attribute_type=='GEOMETRY'
assert original and original.inputs[0].is_linked and multiply and multiply.blend_type=='MULTIPLY'
def linked(source_socket,target_socket):
    return any(link.from_socket==source_socket and link.to_socket==target_socket for link in material.node_tree.links)
assert separate and separate.mode=='RGB' and gate and gate.operation=='GREATER_THAN'
assert not gate.inputs[1].is_linked and abs(gate.inputs[1].default_value-.01)<1e-6
assert linked(attribute.outputs['Color'],separate.inputs[0]) and linked(separate.outputs[0],gate.inputs[0])
assert linked(gate.outputs[0],multiply.inputs[0]),'Missing Color.R source-attribute presence gate'
assert linked(original.outputs[0],multiply.inputs[1]) and linked(attribute.outputs['Color'],multiply.inputs[2])
assert linked(multiply.outputs[0],principled.inputs['Base Color']),'Cavity shader is not enabled on Base Color'
assert game.objects['SM_ImperialSpear'].data.color_attributes.get('PommelCavity') is not None
assert audit['wood_joint']['outside_samples']==0
assert not any(s.name.startswith('TEMP') for s in bpy.data.scenes)
assert not any(o.type=='LIGHT' and o.name.startswith('TEMP Lotus') for o in bpy.data.objects),'Temporary Lotus light objects remain'
assert not any(light.name.startswith('TEMP Lotus') for light in bpy.data.lights),'Temporary Lotus light data remain'
assert not any(world.name.startswith('TEMP Lotus') for world in bpy.data.worlds),'Temporary Lotus inspection worlds remain'
image_paths={im:Path(bpy.path.abspath(im.filepath)).resolve() for im in bpy.data.images if im.source=='FILE' and im.filepath}
assert all(p.is_file() for p in image_paths.values())
source['Spear_revision']='11: curvature-refined four-lobed lotus body, bud V5 and localized cavity shading in shared spearhead gold'
source['PommelDesign']='lotus_bud';source['Pommel_concept_selected']='04 — Lotus bud'
if 'Pommel_concept_accepted' in source:del source['Pommel_concept_accepted']
source['Pommel_body_cross_section']='four-peaked flower';source['Pommel_body_radial_ribs']=4
source['Pommel_secondary_leaf_insets']=geometry['body_design']['secondary_carved_panels'];source['Pommel_bud_revision']='V5'
source['Pommel_body_axial_rows']=geometry['body_design']['curvature_sampled_axial_rows']
source['Pommel_bud_axial_rows']=bud['axial_body_rings'];source['Pommel_bud_lanes_per_petal']=bud['transverse_lanes_per_petal']
source['Pommel_material']='M_ImperialSpear_PBR';source['Pommel_uses_existing_gold']=True
source['Pommel_cavity_attribute']='PommelCavity';source['Pommel_cavity_material_report']='Cavity_Material_Report.json'
source['Pommel_cavity_gate']='COLOR_R_GT_0.01';source['Protected_head_shader_render_check']='Protected_Surface_Render_Check.json'
source['Pommel_unreal_base_color']='BaseColor texture RGB * VertexColor RGB; keep original other inputs'
source['Pommel_model_appearance_accepted']=False;source['Unreal_validated']=False
for scene,filename in [(game,'ImperialSpear_Game.blend'),(source,'ImperialSpear_Source.blend')]:
    bpy.context.window.scene=scene;bpy.ops.object.select_all(action='DESELECT')
    for im,path in image_paths.items():im.filepath=bpy.path.relpath(str(path),start=str(O))
    bpy.ops.wm.save_as_mainfile(filepath=str(O/filename),relative_remap=False)
for im,path in image_paths.items():im.filepath=str(path)
bpy.ops.wm.save_as_mainfile(filepath=str(W/'Working.blend'))
bpy.ops.wm.save_as_mainfile(filepath=str(R/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print('Verified lotus pommel saved to source/game and working files; closing owned Blender.')
bpy.app.timers.register(lambda:bpy.ops.wm.quit_blender(),first_interval=2)
