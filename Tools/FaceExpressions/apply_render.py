import bpy, numpy as np, sys, math, os
from mathutils import Vector
F = '/home/claude/face/'
OUT = F + 'renders/'; os.makedirs(OUT, exist_ok=True)
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
do_render = 'render' in args; do_export = 'export' in args

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath='/mnt/user-data/uploads/Prophecy/Saved/BossUEFNCompatible/20260908_Stitched/SKM_Boss_UEFN_Fitted.fbx')
o = [x for x in bpy.data.objects if x.type == 'MESH'][0]; me = o.data
D = np.load(F + 'boss_deltas.npz'); names = list(D['names'])
inv = np.linalg.inv(np.array(o.matrix_world)[:3, :3])
n = len(me.vertices); base = np.zeros(n * 3); me.vertices.foreach_get('co', base); base = base.reshape(-1, 3)
o.shape_key_add(name='Basis', from_mix=False)
for nm in names:
    k = o.shape_key_add(name=nm, from_mix=False)
    co = base.copy(); co[D[nm + '_idx']] += (inv @ D[nm + '_d'].T).T
    k.data.foreach_set('co', co.ravel())
print('shape keys', [k.name for k in me.shape_keys.key_blocks])

if do_export:
    arm = [x for x in bpy.data.objects if x.type == 'ARMATURE'][0]
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.fbx(filepath=F + 'out/SKM_Boss_UEFN_Fitted_Expressions.fbx', use_selection=True,
        object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False, bake_anim=False, use_mesh_modifiers=False,
        mesh_smooth_type='FACE', use_tspace=False, primary_bone_axis='Y', secondary_bone_axis='X',
        armature_nodetype='NULL', apply_scale_options='FBX_SCALE_NONE', global_scale=1.0, axis_forward='-Z', axis_up='Y')
    print('exported')

if do_render:
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 24; sc.cycles.use_denoising = False
    sc.render.resolution_x = 420; sc.render.resolution_y = 520
    # head framing
    head = np.load(F + 'corr.npz')['b7']
    P = np.array([o.matrix_world @ me.vertices[i].co for i in head])
    c = Vector(P.mean(0)) + Vector((0, 0, 0.04)); h = np.ptp(P[:, 2])
    front = Vector((0, -1, 0))  # boss faces -Y in Blender after import (checked below)
    cam_d = bpy.data.cameras.new('cam'); cam_d.lens = 85
    cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
    # decide facing: nose = head vertex furthest along +/-Y from centre
    teeth = np.load(F + 'corr.npz')['b1']
    T = np.array([o.matrix_world @ me.vertices[i].co for i in teeth]); facing = 1 if T[:, 1].mean() > c.y else -1
    cam.location = c + Vector((0.12 * h, facing * 3.0 * h, 0.03 * h))
    cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.35, 0.36, 0.38, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.6
    L = bpy.data.lights.new('key', 'AREA'); L.energy = 60; L.size = 0.5
    lo = bpy.data.objects.new('key', L); sc.collection.objects.link(lo)
    lo.location = c + Vector((0.6, facing * 0.8, 0.5)); lo.rotation_euler = (c - lo.location).to_track_quat('-Z', 'Y').to_euler()
    cols = {'body': (0.75, 0.55, 0.45), 'head': (0.75, 0.55, 0.45), 'teeth': (0.9, 0.88, 0.8), 'eyeLeft': (0.92, 0.92, 0.92),
            'eyeRight': (0.92, 0.92, 0.92), 'eyeshell': None, 'eyeEdge': None, 'eyelashes': (0.05, 0.04, 0.03)}
    for i, m in enumerate(me.materials):
        key = next((k for k in cols if m.name.startswith(k)), None); col = cols.get(key)
        nm = bpy.data.materials.new('pv' + str(i)); nm.use_nodes = True; bs = nm.node_tree.nodes['Principled BSDF']
        if col is None:
            bs.inputs['Alpha'].default_value = 0.0
        else:
            bs.inputs['Base Color'].default_value = (*col, 1); bs.inputs['Roughness'].default_value = 0.55
        me.materials[i] = nm
    # eye irises: dark disc via simple trick not needed; keep plain
    for kb in me.shape_keys.key_blocks: kb.value = 0
    shots = ['Neutral'] + names
    for s in shots:
        for kb in me.shape_keys.key_blocks[1:]: kb.value = 1.0 if kb.name == s else 0.0
        sc.render.filepath = OUT + s + '.png'; bpy.ops.render.render(write_still=True)
        print('rendered', s)
