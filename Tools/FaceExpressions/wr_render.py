import bpy, numpy as np, os
from mathutils import Vector
F = '/home/claude/face/'; OUT = F + 'renders/wr/'; os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=F + 'out/SKM_Boss_UEFN_Fitted_Expressions.fbx')
o = [x for x in bpy.data.objects if x.type == 'MESH'][0]; me = o.data
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 32; sc.cycles.use_denoising = False
sc.render.resolution_x = 460; sc.render.resolution_y = 520
corr = np.load(F + 'corr.npz')
P = np.array([o.matrix_world @ me.vertices[i].co for i in corr['b7']]); T = np.array([o.matrix_world @ me.vertices[i].co for i in corr['b1']])
c = Vector(P.mean(0)) + Vector((0, 0, 0.05)); h = np.ptp(P[:, 2]); facing = 1 if T[:, 1].mean() > c.y else -1
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); cam.data.lens = 85; sc.collection.objects.link(cam); sc.camera = cam
cam.location = c + Vector((0.1 * h, facing * 2.2 * h, 0.0)); cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.3, 0.31, 0.33, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.35
L = bpy.data.lights.new('key', 'AREA'); L.energy = 45; L.size = 0.25
lo = bpy.data.objects.new('key', L); sc.collection.objects.link(lo)
lo.location = c + Vector((0.35, facing * 0.5, 0.55)); lo.rotation_euler = (c - lo.location).to_track_quat('-Z', 'Y').to_euler()
img = lambda p, cs: (lambda i: (setattr(i.colorspace_settings, 'name', cs), i)[1])(bpy.data.images.load(p))
col = img(F + 'dnacal/data/maps/head_color_map.tga', 'sRGB')
head = bpy.data.materials.new('head'); head.use_nodes = True; nt = head.node_tree; bs = nt.nodes['Principled BSDF']
tc = nt.nodes.new('ShaderNodeTexImage'); tc.image = col; nt.links.new(tc.outputs[0], bs.inputs['Base Color'])
tn = nt.nodes.new('ShaderNodeTexImage'); nm = nt.nodes.new('ShaderNodeNormalMap')
nt.links.new(tn.outputs[0], nm.inputs['Color']); nt.links.new(nm.outputs[0], bs.inputs['Normal'])
bs.inputs['Roughness'].default_value = 0.5; bs.inputs['Subsurface Weight'].default_value = 0.15
plain = {}
for i, m in enumerate(me.materials):
    if m.name.startswith('head'): me.materials[i] = head; continue
    k = 'teeth' if 'teeth' in m.name else 'eye' if m.name.startswith('eyeL') or m.name.startswith('eyeR') else 'lash' if 'lash' in m.name else 'clear' if ('shell' in m.name or 'Edge' in m.name) else 'body'
    pm = bpy.data.materials.new(k + str(i)); pm.use_nodes = True; b = pm.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = {'teeth': (0.85, 0.82, 0.74, 1), 'eye': (0.9, 0.9, 0.9, 1), 'lash': (0.03, 0.02, 0.02, 1), 'clear': (1, 1, 1, 1), 'body': (0.62, 0.45, 0.38, 1)}[k]
    if k == 'clear': b.inputs['Alpha'].default_value = 0
    me.materials[i] = pm
nmaps = {}
def N(name):
    if name not in nmaps: nmaps[name] = img(F + f'out/wrinkles/preview/{name}_N.png', 'Non-Color')
    return nmaps[name]
shots = [('Neutral', 'Neutral')] + [(e, v) for e in ['Anger', 'Fear', 'Pain', 'Effort', 'Grin', 'Shout'] for v in ('Neutral', e)]
for e, nmap in shots:
    for kb in me.shape_keys.key_blocks[1:]: kb.value = 1.0 if kb.name == e else 0.0
    tn.image = N(nmap)
    sc.render.filepath = OUT + f'{e}__{"wrinkles" if nmap != "Neutral" else "plain"}.png'
    bpy.ops.render.render(write_still=True); print('rendered', sc.render.filepath)
