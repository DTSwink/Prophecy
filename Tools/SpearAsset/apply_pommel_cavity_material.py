"""Darken authored pommel cavities in the original shared gold material only.

PommelCavity is CORNER/FLOAT_COLOR: linear grayscale RGB=1-.55*mask, A=1.
Missing Attribute Color.R is zero; valid authored shade is at least0.45.
Color.R >0.01 gates the multiply, retaining the original surface when absent.
Attribute alpha is deliberately not used as a presence signal in Blender5.1.
No source color layers, texture files, roughness, normals or metal wiring change.
"""
import bpy,json,math
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
WORK=ROOT/'Saved/Diagnostics/ImperialSpear/PommelLotus'
NAME='PommelCavity';PREFIX='PommelCavity_'
art=bpy.data.collections['SPEAR • editable components']
mat=bpy.data.materials['M_ImperialSpear_PBR'];nodes=mat.node_tree.nodes;links=mat.node_tree.links
principled=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
protected={o.name:[(a.name,a.domain,a.data_type) for a in o.data.color_attributes]
           for o in art.objects if o.type=='MESH' and not o.name.startswith(('02 •','Pommel •'))}
rows=[]
for ob in art.objects:
    if ob.type!='MESH':continue
    layer=ob.data.color_attributes.get(NAME)
    if layer is None:continue
    assert ob.name.startswith(('02 •','Pommel •')),('Cavity attribute on a protected component',ob.name)
    assert layer.domain=='CORNER' and layer.data_type=='FLOAT_COLOR',(ob.name,layer.domain,layer.data_type)
    colors=[tuple(c.color) for c in layer.data]
    assert len(colors)==len(ob.data.loops) and colors
    assert all(all(math.isfinite(v) for v in c) and .45-1e-6<=c[0]<=1+1e-6
               and max(abs(c[0]-c[i]) for i in (1,2))<1e-6 and abs(c[3]-1)<1e-6 for c in colors),('Expected neutral linear shade RGBA',ob.name)
    rows.append({'object':ob.name,'corners':len(colors),'minimum_shade':min(c[0] for c in colors),
                 'maximum_shade':max(c[0] for c in colors),'darkened_corners':sum(c[0]<.99999 for c in colors)})
assert rows and any(r['darkened_corners'] for r in rows),'No authored dark cavity colors'

# Capture the accepted Base Color input once. Re-running this script must not
# capture its own previous multiplier and accidentally compound the darkening.
original=nodes.get(PREFIX+'BaseOriginal')
if original is None:
    incoming=list(principled.inputs['Base Color'].links)
    original=nodes.new('NodeReroute');original.name=PREFIX+'BaseOriginal'
    original.label='Accepted Base Color (unchanged)'
    if incoming:links.new(incoming[0].from_socket,original.inputs[0])
    else:
        constant=nodes.new('ShaderNodeRGB');constant.name=PREFIX+'OriginalConstant'
        constant.outputs[0].default_value=principled.inputs['Base Color'].default_value
        links.new(constant.outputs[0],original.inputs[0])
assert original.inputs[0].is_linked,'Missing retained original Base Color input'
for node in list(nodes):
    if node.name.startswith(PREFIX) and node not in (original,nodes.get(PREFIX+'OriginalConstant')):
        nodes.remove(node)

attribute=nodes.new('ShaderNodeAttribute');attribute.name=PREFIX+'Attribute'
attribute.attribute_name=NAME;attribute.attribute_type='GEOMETRY'
attribute.label='Pommel shade; absent Color.R = 0'
separate=nodes.new('ShaderNodeSeparateColor');separate.name=PREFIX+'SeparateShade'
separate.mode='RGB';separate.label='Read neutral shade R'
gate=nodes.new('ShaderNodeMath');gate.name=PREFIX+'PresenceGate'
gate.operation='GREATER_THAN';gate.inputs[1].default_value=.01
gate.label='Present shade R > 0.01'
links.new(attribute.outputs['Color'],separate.inputs[0])
links.new(separate.outputs[0],gate.inputs[0])
multiply=nodes.new('ShaderNodeMixRGB');multiply.name=PREFIX+'BaseMultiply'
multiply.blend_type='MULTIPLY';multiply.use_clamp=False
multiply.label='Original gold × authored cavity shade'
links.new(gate.outputs[0],multiply.inputs[0])
links.new(original.outputs[0],multiply.inputs[1])
links.new(attribute.outputs['Color'],multiply.inputs[2])
links.new(multiply.outputs[0],principled.inputs['Base Color'])
original.location=(principled.location.x-520,principled.location.y+200)
attribute.location=(principled.location.x-520,principled.location.y-40)
separate.location=(principled.location.x-520,principled.location.y-260)
gate.location=(principled.location.x-280,principled.location.y-220)
multiply.location=(principled.location.x-240,principled.location.y+120)
mat['PommelCavityEnabled']=True
mat['PommelCavityEncoding']='linear grayscale RGB=1-.55*mask; alpha1; missing Color.R0 bypasses multiply'
mat['PommelCavityGate']='COLOR_R_GT_0.01'
mat['PommelCavityRoughnessChanged']=False
for name,state in protected.items():
    assert [(a.name,a.domain,a.data_type) for a in art.objects[name].data.color_attributes]==state
report={'material':mat.name,'attribute':NAME,'encoding':'linear grayscale RGB multiplier; alpha1',
        'source_missing_attribute_behavior':'Color.R0 fails >0.01 presence gate -> original Base Color exactly',
        'source_presence_gate':'Color.R > 0.01; valid shades are 0.45..1; attribute alpha is not a presence signal',
        'protected_source_color_layers_modified':False,'protected_components':len(protected),
        'original_textures_changed':False,'roughness_metallic_normal_specular_changed':False,
        'components':rows,'unreal_wiring':'BaseColor texture RGB multiplied by VertexColor RGB; keep existing other material connections',
        'glb_wiring':'Original BaseColor texture plus standard COLOR_0 multiplication exactly once'}
(WORK/'Cavity_Material_Report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
