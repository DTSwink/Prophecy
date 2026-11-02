"""Inspect interpolated surface normals without texture or light response."""
import bpy
from pathlib import Path
p=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Tools/SpearAsset/render_lotus_gold.py')
parts=[o for o in bpy.data.collections['SPEAR • editable components'].objects if o.type=='MESH' and o.name.startswith(('02 •','Pommel •'))]
saved=[(o,o.data.materials[0]) for o in parts]
mat=bpy.data.materials.new('TEMP Lotus normal diagnostic');mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;n.clear()
geometry=n.new('ShaderNodeNewGeometry');scale=n.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs[3].default_value=.5
offset=n.new('ShaderNodeVectorMath');offset.operation='ADD';offset.inputs[1].default_value=(.5,.5,.5)
emission=n.new('ShaderNodeEmission');out=n.new('ShaderNodeOutputMaterial')
l.new(geometry.outputs['Normal'],scale.inputs[0]);l.new(scale.outputs[0],offset.inputs[0]);l.new(offset.outputs[0],emission.inputs[0]);l.new(emission.outputs[0],out.inputs[0])
try:
    for ob,old in saved:ob.data.materials[0]=mat
    code=p.read_text(encoding='utf-8').replace("('Gold_'+view+'.png')","('Normals_'+view+'.png')").replace('s.cycles.samples=96','s.cycles.samples=8')
    exec(compile(code,str(p),'exec'),{'LOTUS_VIEW':'reference'})
finally:
    for ob,old in saved:ob.data.materials[0]=old
    bpy.data.materials.remove(mat)
