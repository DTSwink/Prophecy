"""Geometry-only comparison; restore exact original assignments and lighting."""
import bpy
from pathlib import Path
p=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Tools/SpearAsset/render_lotus_gold.py')
art=bpy.data.collections['SPEAR • editable components']
parts=[o for o in art.objects if o.type=='MESH' and o.name.startswith(('02 •','Pommel •'))]
saved=[(o,o.data.materials[0]) for o in parts]
mat=bpy.data.materials.new('TEMP Lotus plain metal');mat.use_nodes=True
pr=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
pr.inputs['Base Color'].default_value=(.58,.36,.12,1);pr.inputs['Metallic'].default_value=1;pr.inputs['Roughness'].default_value=.30
try:
    for ob,old in saved:ob.data.materials[0]=mat
    code=p.read_text(encoding='utf-8').replace("('Gold_'+view+'.png')","('Plain_'+view+'.png')")
    exec(compile(code,str(p),'exec'),{'LOTUS_VIEW':'reference'})
finally:
    for ob,old in saved:ob.data.materials[0]=old
    bpy.data.materials.remove(mat)
print('Plain-metal diagnostic complete; shared gold restored.')
