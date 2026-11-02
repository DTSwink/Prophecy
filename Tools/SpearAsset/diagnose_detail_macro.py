"""Same-axis close inspection; restore the presentation camera after both passes."""
import bpy, math, json
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene']; bpy.context.window.scene=s; cam=s.camera
state=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples,s.cycles.use_denoising)
art=bpy.data.collections['SPEAR • editable components']; blade=next(o for o in art.objects if o.name.startswith('06 •')); mat=blade.data.materials[0]
report={o.name:[{'name':u.name,'active_render':u.active_render} for u in o.data.uv_layers] for o in art.objects if o.type=='MESH'}
report['normal_node']={'strength':mat.node_tree.nodes['Normal Map'].inputs['Strength'].default_value,'uv_map':mat.node_tree.nodes['Normal Map'].uv_map}
(OUT/'Detail_UV_Diagnosis.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
ax,ay=s['Reference_camera_axis']; cx,cy=700,335; scale=.00096
cam.location=(((cx-172)*ay-(cy-9)*ax)*scale,-3,2.2-((cx-172)*ax+(cy-9)*ay)*scale)
cam.data.ortho_scale=520*scale; s.render.resolution_x=1300; s.render.resolution_y=700
output=next(n for n in mat.node_tree.nodes if n.type=='OUTPUT_MATERIAL'); principled=mat.node_tree.nodes['Principled BSDF']; temporary=None
try:
 s.cycles.samples=24; s.cycles.use_denoising=True; s.render.filepath=str(OUT/'Comparison_DetailMacro.png'); bpy.ops.render.render(write_still=True)
 temporary=mat.node_tree.nodes.new('ShaderNodeEmission'); mat.node_tree.links.new(mat.node_tree.nodes['Atlas_base'].outputs['Color'],temporary.inputs['Color']); mat.node_tree.links.new(temporary.outputs[0],output.inputs['Surface'])
 s.cycles.samples=1; s.cycles.use_denoising=False; s.render.filepath=str(OUT/'Diagnostic_BaseColorMacro.png'); bpy.ops.render.render(write_still=True)
finally:
 mat.node_tree.links.new(principled.outputs['BSDF'],output.inputs['Surface'])
 if temporary: mat.node_tree.nodes.remove(temporary)
 cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples,s.cycles.use_denoising=state
print('Same-axis shaded and base-color macros saved; main camera and material restored.')
