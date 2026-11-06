"""Dialogue Lab asset build (runs inside Blender, on the laptop: no downloads).

blender -b --factory-startup -P lab_build.py -- <boss.fbx> <idle.fbx> <scene.npz> <scene_meta.json> <lab_dir> [levels.npz]

[levels.npz]: emotion-gain levels expressed in the scene npz's PCA basis (levels, c_S1/c_S2 [L,F,K], w_S1/w_S2 [L,F,82]);
they replace the scene's single (approved 1.6) face/wrinkle tracks and drive the lab's Emotion slider

- Boss mesh + 87-bone UEFN skeleton (fingers included) -> data/boss.glb
- face: the scene's PCA vertex-delta basis becomes morph targets ('mu' + 'pc0..pcK-1'), so a frame of face animation is
  just K morph weights (exact same deltas as the Blender renders)
- body: the game idle (Anim_Idle.fbx = M_Neutral_Stand_Idle_Loop, 301 f @ 30 fps) retargeted onto the Boss rest pose by
  copying parent-space rotations (Unreal-style same-skeleton retarget; the Boss rest is an A-pose, the clip's is not)
- per-frame data (PCA weights, wrinkle-map weights, head angles) -> data/scene.bin + data/scene.json
"""
import bpy, sys, os, json, numpy as np
from mathutils import Matrix

a = sys.argv[sys.argv.index('--') + 1:]
POSES = None
if '--poses' in a: i = a.index('--poses'); POSES = a[i + 1]; a = a[:i] + a[i + 2:]   # speech-pose FBX (one pose per frame)
SKIP = set()   # source frames of the pose FBX to leave out (user: frame 4 = "pose 3" was dropped on Nov 6)
if '--poses-skip' in a: i = a.index('--poses-skip'); SKIP = {int(x) for x in a[i + 1].split(',') if x}; a = a[:i] + a[i + 2:]
BOSS, IDLE, NPZ, META, LAB = a[:5]; LEVELS_NPZ = a[5] if len(a) > 5 else None
os.makedirs(os.path.join(LAB, 'data'), exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)

def imp(path):
    before = set(bpy.data.objects)
    if hasattr(bpy.ops.wm, 'fbx_import'): bpy.ops.wm.fbx_import(filepath=path)
    else: bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before]

bo = imp(BOSS); arm_b = [o for o in bo if o.type == 'ARMATURE'][0]; mesh = [o for o in bo if o.type == 'MESH'][0]
ao = imp(IDLE); arm_a = [o for o in ao if o.type == 'ARMATURE'][0]
act = arm_a.animation_data.action
f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
sc = bpy.context.scene; sc.render.fps = 30

# ---------- retarget idle: copy parent-space transforms ----------
def rest_rel(arm, n):
    b = arm.data.bones[n]
    return (b.parent.matrix_local.inverted() @ b.matrix_local) if b.parent else b.matrix_local.copy()
names = [b.name for b in arm_b.data.bones]
RR = {n: (rest_rel(arm_a, n), rest_rel(arm_b, n)) for n in names}
TRANSLATE = {'attach', 'pelvis', 'root'}
# Bones copied as a DELTA from rest instead of as the absolute parent-space rotation. The fitted Boss rig's foot_l rest
# frame is twisted ~24 deg about the bone axis relative to the mannequin (foot_r: 6 deg, everything else symmetric L/R),
# so the absolute copy rolls the left sole (5 deg tilt, sinks under the floor). The delta keeps the Boss's flat bind
# foot and applies the idle's motion on top (sole tilt 0.7 deg).
DELTA = {'foot_l'}
arm_b.animation_data_create()
for pb in arm_b.pose.bones: pb.rotation_mode = 'QUATERNION'
def retarget(arm_src, f0, f1, name, frames=None):
    """copy frames f0..f1 (or the given list) of arm_src's active action onto the Boss as a new action, keyed 0,1,2..."""
    RRs = {n: (rest_rel(arm_src, n), rest_rel(arm_b, n)) for n in names}
    act_new = bpy.data.actions.new(name); arm_b.animation_data.action = act_new
    frames = frames or list(range(f0, f1 + 1))
    for key, f in enumerate(frames):
        sc.frame_set(f)
        for n in names:
            pa = arm_src.pose.bones[n]; ra, rb = RRs[n]
            local_a = ra @ pa.matrix_basis
            if n in TRANSLATE:
                basis = rb.inverted() @ local_a
            elif n in DELTA:
                q = ra.to_quaternion().inverted() @ local_a.to_quaternion()
                basis = q.to_matrix().to_4x4()
            else:
                q = rb.to_quaternion().inverted() @ local_a.to_quaternion()
                basis = Matrix.Translation((0, 0, 0)) @ q.to_matrix().to_4x4()
            pbb = arm_b.pose.bones[n]
            loc, rot, _ = basis.decompose()
            pbb.location = loc if n in TRANSLATE else (0, 0, 0); pbb.rotation_quaternion = rot
            pbb.keyframe_insert('location', frame=key); pbb.keyframe_insert('rotation_quaternion', frame=key)
    return act_new
act_p = None; POSE_FRAMES = None
if POSES:   # speech poses first (frame 1 = idle reference, then one pose per frame), the idle stays the active action
    po = imp(POSES); arm_p = [o for o in po if o.type == 'ARMATURE'][0]; ap = arm_p.animation_data.action
    p0, p1 = int(ap.frame_range[0]), int(ap.frame_range[1])
    keep = [f for f in range(p0, p1 + 1) if f not in SKIP]
    act_p = retarget(arm_p, p0, p1, 'Poses', keep); POSE_FRAMES = keep; print('POSES', len(keep), 'frames kept of', p1 - p0 + 1, 'skipped', sorted(SKIP))
    for o in po: bpy.data.objects.remove(o, do_unlink=True)
act_b = retarget(arm_a, f0, f1, 'Idle')
sc.frame_start, sc.frame_end = 0, f1 - f0
# retarget check: source vs target joint positions (armature-object world, relative to pelvis) at the first frame
def wpos(arm, n): return arm.matrix_world @ arm.pose.bones[n].head
sc.frame_set(f0); src = {n: wpos(arm_a, n) - wpos(arm_a, 'pelvis') for n in ('clavicle_r', 'upperarm_r', 'hand_r', 'head', 'index_03_r')}
sc.frame_set(0); dst = {n: wpos(arm_b, n) - wpos(arm_b, 'pelvis') for n in src}
for n in src: print('RT', n, [round(x, 3) for x in src[n]], [round(x, 3) for x in dst[n]])
for o in ao: bpy.data.objects.remove(o, do_unlink=True)
for x in list(bpy.data.actions):   # only the retargeted idle goes into the glb
    if x not in (act_b, act_p): bpy.data.actions.remove(x)
if act_p:   # both actions must reach the glb: park the poses on an NLA track, idle stays active
    tr = arm_b.animation_data.nla_tracks.new(); tr.name = 'Poses'; tr.strips.new('Poses', 0, act_p); tr.mute = True

# ---------- face morph targets from the scene PCA basis ----------
A = np.load(NPZ)
bidx = A['bidx']; mu = A['mu'].astype(np.float64).reshape(-1, 3); basis = A['basis'].astype(np.float64)
K = basis.shape[0]; basis = basis.reshape(K, -1, 3)
inv = np.linalg.inv(np.array(mesh.matrix_world)[:3, :3])
me = mesh.data; n = len(me.vertices)
base = np.zeros(n * 3); me.vertices.foreach_get('co', base); base = base.reshape(-1, 3)
mesh.shape_key_add(name='Basis', from_mix=False)
def add_key(name, d):
    co = base.copy(); co[bidx] += d @ inv.T
    k = mesh.shape_key_add(name=name, from_mix=False); k.data.foreach_set('co', co.ravel()); k.value = 0.0
add_key('mu', mu)
for i in range(K): add_key(f'pc{i}', basis[i])

# ---------- per-frame data ----------
meta = json.load(open(META))
parts, offs, buf = {}, 0, []
# emotion-gain levels (dialog_levels.npz: c/w are [level, frame, ...]); a single-level npz is the approved gain 1.6
Lv = np.load(LEVELS_NPZ) if LEVELS_NPZ else A
levels = [float(x) for x in Lv['levels']] if 'levels' in Lv.files else [1.6]
for key in ('c_S1', 'c_S2', 'w_S1', 'w_S2', 'h_S1', 'h_S2'):
    arr = (Lv if key[0] in 'cw' else A)[key].astype(np.float32)
    if key[0] in 'cw' and arr.ndim == 2: arr = arr[None]
    buf.append(arr.ravel()); parts[key] = dict(offset=offs, shape=list(arr.shape)); offs += arr.size
np.concatenate(buf).astype('<f4').tofile(os.path.join(LAB, 'data', 'scene.bin'))
# facing of the character in glTF coordinates (Blender (x, y, z) -> glTF (x, z, -y))
P = np.array([mesh.matrix_world @ v.co for v in me.vertices])
mats = [m.name for m in me.materials]
def verts_of(prefix):
    ids = [i for i, nm in enumerate(mats) if nm.startswith(prefix)]
    return np.array(sorted({v for p in me.polygons if p.material_index in ids for v in p.vertices}))
hc = P[verts_of('head')].mean(0); facing = 1 if P[verts_of('teeth')][:, 1].mean() > hc[1] else -1
meta.update(dict(K=K, fps=float(A['fps']), frames=int(A['h_S1'].shape[0]), levels=levels, parts=parts, mapNames=[str(x) for x in A['names']],
                 forwardGltf=[0, 0, -facing], headCenterGltf=[float(hc[0]), float(hc[2]), float(-hc[1])],
                 idleFrames=f1 - f0 + 1, materials=mats, poseFrames=POSE_FRAMES))
json.dump(meta, open(os.path.join(LAB, 'data', 'scene.json'), 'w'), indent=1)

# ---------- export ----------
bpy.ops.object.select_all(action='DESELECT')
arm_b.select_set(True); mesh.select_set(True); bpy.context.view_layer.objects.active = arm_b
bpy.ops.export_scene.gltf(filepath=os.path.join(LAB, 'data', 'boss.glb'), export_format='GLB', use_selection=True,
                          export_animations=True, export_morph=True, export_morph_normal=True, export_skins=True,
                          export_yup=True, export_apply=False, export_materials='EXPORT', export_image_format='NONE', export_force_sampling=True,
                          export_frame_range=True)
print('LAB BUILD OK', K, 'morphs', f1 - f0 + 1, 'idle frames', os.path.getsize(os.path.join(LAB, 'data', 'boss.glb')) // 1024, 'KB glb')
