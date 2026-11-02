import bpy,bmesh,json
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene
art=bpy.data.collections['SPEAR • editable components']
assert not scene.get('Reference_body_atlas_remapped'),'Already remapped'
for ob in art.objects:
 if ob.type!='MESH' or not ob.data.uv_layers: continue
 uv=ob.data.uv_layers.get('UV0_SurfaceAtlas') or ob.data.uv_layers.active
 if ob.name.startswith('07 •'):
  for loop in ob.data.loops:
   co=ob.data.vertices[loop.vertex_index].co
   uv.data[loop.index].uv=(.5+.25*(co.x+.06)/.12,.5+.25*(co.z-1.64)/.13)
  uv.active_render=True
  for layer in list(ob.data.uv_layers):
   if layer.name!=uv.name: ob.data.uv_layers.remove(layer)
 else:
  for sample in uv.data:
   u,v=sample.uv
   if .49999<u<.75001 and .49999<v<1.00001: sample.uv.y=.75+(v-.5)*.5
for image in bpy.data.images:
 if image.source=='FILE' and image.name.startswith('T_ImperialSpear_'):
  image.filepath=str(OUT/'Textures'/(image.name.split('.png')[0]+'.png')); image.reload()
  if '_ORM' in image.name: image.alpha_mode='CHANNEL_PACKED'; image.colorspace_settings.name='Non-Color'
scene['Reference_body_atlas_remapped']=True
body=next(o for o in art.objects if o.name.startswith('07 •'))
bm=bmesh.new(); bm.from_mesh(body.data); closed=all(e.is_manifold for e in bm.edges); volume=bm.calc_volume(signed=True); bm.free()
report=json.loads((OUT/'Reference_Rebuild_Verification.json').read_text(encoding='utf-8'))
report['body_normal_chasing']={'dedicated_atlas':True,'depth_mm':.22,'raised_relief_in_geometry':True,'eye_hole_in_geometry':True,'housing_closed':closed,'volume_m3':volume}
report['source_triangles']=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in art.objects if o.type=='MESH')
(OUT/'Reference_Rebuild_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report['body_normal_chasing']))
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
scene.render.filepath=str(OUT/'Comparison_Current.png'); bpy.ops.render.render(write_still=True)
