import bpy
from pathlib import Path
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');m=bpy.data.materials['M_ImperialSpear_PBR'];nodes=m.node_tree.nodes
uv=nodes.get('Explicit surface atlas UV') or nodes.new('ShaderNodeUVMap');uv.name='Explicit surface atlas UV';uv.uv_map='UV0_SurfaceAtlas'
for n in [x for x in nodes if x.type=='TEX_IMAGE']:
 old=n.image;path=bpy.path.abspath(old.filepath);name=old.name;space=old.colorspace_settings.name;alpha=old.alpha_mode
 old.name=name+' stale-cache recovery'
 im=bpy.data.images.load(path,check_existing=False);im.name=name;im.colorspace_settings.name=space;im.alpha_mode=alpha
 n.image=im;m.node_tree.links.new(uv.outputs['UV'],n.inputs['Vector'])
 if old.users==0:bpy.data.images.remove(old)
 print(n.name,im.name,list(im.size),space)
m.node_tree.update_tag();bpy.context.view_layer.update()
exec(compile((R/'Tools/SpearAsset/render_handle_review.py').read_text(encoding='utf-8'),'render_handle_review.py','exec'))
