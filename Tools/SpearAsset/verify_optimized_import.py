"""Independent Blender FBX readback of the SDK-written optimized candidate."""
from pathlib import Path
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');O=R/'Saved/Diagnostics/ImperialSpear/Optimization20261028'
code=(R/'Tools/SpearAsset/verify_exports.py').read_text(encoding='utf-8')
exec(compile(code[:code.index('def verify_glb_cavity')],'<verification helpers>','exec'))
import numpy as np
source=bpy.data.scenes['Scene'];game=bpy.data.scenes['GAME • Unreal export'];render=game.objects['SM_ImperialSpear']
before=set(bpy.data.objects);read=bpy.data.scenes.new('TEMP optimized FBX readback');bpy.context.window.scene=read
try:
 bpy.ops.import_scene.fbx(filepath=str(O/'SM_ImperialSpear.fbx'),use_custom_normals=True,colors_type='LINEAR',use_image_search=False)
 objects=[o for o in bpy.data.objects if o not in before]
 imported=next(o for o in objects if o.type=='MESH' and not o.name.startswith('UCX_'))
 assert len(imported.data.polygons)==len(render.data.polygons)
 audit=surface_readback_error(render,imported)
 hulls=[o for o in objects if o.name.startswith('UCX_')];sockets=[o for o in objects if o.name.startswith('SOCKET_')]
 assert len(hulls)==17 and len(sockets)==4
 assert len(imported.data.uv_layers)==2
 report={'status':'PASS','triangles':len(imported.data.polygons),'hulls':len(hulls),'sockets':len(sockets),'surface':audit}
 (O/'Blender_FBX_Readback.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report))
finally:
 bpy.context.window.scene=source
 for o in list(bpy.data.objects):
  if o not in before:bpy.data.objects.remove(o,do_unlink=True)
 bpy.data.scenes.remove(read)
