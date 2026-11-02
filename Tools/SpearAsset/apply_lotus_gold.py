"""Attach isolated calibrated pommel gold; keep the accepted spear atlas intact."""
import bpy,json,shutil,hashlib
from pathlib import Path
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');W=R/'Saved/Diagnostics/ImperialSpear/PommelLotus'
O=R/'Exports/ImperialSpear/PommelTextures';O.mkdir(exist_ok=True)
old=R/'Exports/ImperialSpear/Textures'
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in old.glob('*.png')}
mat=bpy.data.materials['M_ImperialSpear_PommelGold'];mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;n.clear()
pr=n.new('ShaderNodeBsdfPrincipled');pr.location=(450,0)
out=n.new('ShaderNodeOutputMaterial');out.location=(740,0);l.new(pr.outputs['BSDF'],out.inputs['Surface'])
pr.inputs['Alpha'].default_value=1;pr.inputs['Coat Weight'].default_value=0
images={}
for kind in ('BaseColor','ORM','NormalGL','NormalDX'):
    name='T_ImperialSpear_LotusGold_'+kind+'.png';src=W/'Gold'/name;dst=O/name
    assert src.is_file(),str(src);shutil.copy2(src,dst)
    im=bpy.data.images.load(str(dst),check_existing=True);im.reload();im.colorspace_settings.name='sRGB' if kind=='BaseColor' else 'Non-Color'
    if kind=='ORM':im.alpha_mode='CHANNEL_PACKED'
    images[kind]=im
    if kind=='NormalDX':continue
    t=n.new('ShaderNodeTexImage');t.image=im;t.interpolation='Linear';t.extension='REPEAT';t.name='Pommel '+kind
    t.location=(-550,{'BaseColor':260,'ORM':0,'NormalGL':-310}[kind])
    if kind=='BaseColor':l.new(t.outputs['Color'],pr.inputs['Base Color'])
    elif kind=='ORM':
        sep=n.new('ShaderNodeSeparateColor');sep.location=(-220,10);l.new(t.outputs['Color'],sep.inputs['Color'])
        l.new(sep.outputs['Green'],pr.inputs['Roughness']);l.new(sep.outputs['Blue'],pr.inputs['Metallic']);l.new(t.outputs['Alpha'],pr.inputs['Specular IOR Level'])
    else:
        nm=n.new('ShaderNodeNormalMap');nm.location=(0,-260);nm.inputs['Strength'].default_value=1;nm.uv_map='UV0_SurfaceAtlas'
        l.new(t.outputs['Color'],nm.inputs['Color']);l.new(nm.outputs['Normal'],pr.inputs['Normal'])
assert hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in old.glob('*.png')}
report={'material':mat.name,'textures':{k:str(im.filepath) for k,im in images.items()},'existing_atlas_hashes_unchanged':hashes,'material_slots_full_asset':2}
(W/'Material_Application.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(W/'Working.blend'))
print(json.dumps(report))
