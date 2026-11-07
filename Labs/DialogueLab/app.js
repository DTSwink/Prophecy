// Dialogue Lab: two Boss characters, Unreal-driven face/head (our dialogue pipeline), game idle body with fingers.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';
import { loadPoses, createPoser, weightAt, motionLength, poseNames, poseArms, DEFAULT_PARAMS } from './motion.js';
import { planSpeech } from './speech.js';
import { planGaze, gazeAt } from './gaze.js';

const $ = (id) => document.getElementById(id);
const meta = await (await fetch('data/scene.json')).json();
const bin = new Float32Array(await (await fetch('data/scene.bin')).arrayBuffer());
// per-frame tracks; face (c) and wrinkle (w) tracks have one copy per emotion-gain level: [level][frame][k]
const part = (key) => { const p = meta.parts[key], sh = p.shape; return { a: bin.subarray(p.offset, p.offset + sh.reduce((x, y) => x * y, 1)),
  w: sh[sh.length - 1], lv: sh.length === 3 ? sh[0] : 1, fs: sh[sh.length - 2] * sh[sh.length - 1] }; };
const LEVELS = (meta.levels || [1.6]).map((v) => +(+v).toFixed(3));  // float32 in the json
const FPS = meta.fps, NF = meta.frames, K = meta.K, T = meta.T;
$('scene').textContent = '· ' + meta.scene;

// ---------- renderer / scene ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.AgXToneMapping; renderer.toneMappingExposure = 1.25;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
$('view').appendChild(renderer.domElement);
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x3b3f45);
scene.fog = new THREE.Fog(0x3b3f45, 12, 40);
const camera = new THREE.PerspectiveCamera(30, innerWidth / innerHeight, 0.05, 200);
const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true;
addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });

const ground = new THREE.Mesh(new THREE.CircleGeometry(30, 64), new THREE.MeshStandardMaterial({ color: 0x6f6553, roughness: 0.95 }));
ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);

// ---------- textures ----------
const tl = new THREE.TextureLoader();
const tex = (f, srgb) => { const t = tl.load('assets/tex/' + f); t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace; t.flipY = false; t.anisotropy = 8; return t; };
const bl = new THREE.ImageBitmapLoader(); bl.setOptions({ imageOrientation: 'none', premultiplyAlpha: 'none', colorSpaceConversion: 'none' });
// 37 MetaHuman region masks, 4 per RGBA tile, 10 tiles in one 4x3 atlas (one sampler: GPUs allow only 16 per shader)
const atlas = await new Promise((res) => bl.load('assets/maskpack/mask_atlas.png', (img) => {
  const t = new THREE.Texture(img); t.flipY = false; t.colorSpace = THREE.NoColorSpace; t.premultiplyAlpha = false;
  t.generateMipmaps = false; t.minFilter = THREE.LinearFilter; t.needsUpdate = true; res(t);
}));
const T_ = {
  color: tex('head_color_map.png', 1), normal: tex('head_normal_map.png', 0), rough: tex('head_roughness_map.png', 0),
  cm: [1, 2, 3].map((i) => tex(`head_cm${i}_color_map.png`, 1)), wm: [1, 2, 3].map((i) => tex(`head_wm${i}_normal_map.png`, 0)),
  eyes: tex('eyes_color_map.png', 1), teeth: tex('teeth_color_map.png', 1), lash: tex('eyelashes_color_map.png', 1),
};

// wrinkle / blood-flow map weights: 82 animated-map entries -> 6 maps x 10 packs x vec4 (MetaHuman region masks)
const MAPS = ['head_cm1_color', 'head_cm2_color', 'head_cm3_color', 'head_wm1_normal', 'head_wm2_normal', 'head_wm3_normal'];
const REGS = [...new Set(meta.mapNames.map((n) => n.split('.')[1]))].sort();
const slot = meta.mapNames.map((n) => { const [mp, rg] = n.split('.'); const r = REGS.indexOf(rg); return [MAPS.indexOf(mp), r >> 2, r & 3]; });

function headMaterial() {
  const m = new THREE.MeshStandardMaterial({ map: T_.color, normalMap: T_.normal, roughnessMap: T_.rough, roughness: 0.85 });
  // MetaHuman normal maps are DirectX (green down); with glTF UVs (flipY false) three's tangent frame is already flipped,
  // so the two flips cancel: normalScale stays (1, 1)
  const U = { uW: { value: Array.from({ length: 60 }, () => new THREE.Vector4()) }, uWrinkle: { value: 1 }, mkAtlas: { value: atlas },
    cm1: { value: T_.cm[0] }, cm2: { value: T_.cm[1] }, cm3: { value: T_.cm[2] }, wm1: { value: T_.wm[0] }, wm2: { value: T_.wm[1] }, wm3: { value: T_.wm[2] } };
  m.userData.U = U;
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, U);
    const decl = `uniform vec4 uW[60]; uniform float uWrinkle; uniform sampler2D cm1, cm2, cm3, wm1, wm2, wm3, mkAtlas;
      float wA[6];
      void wrinkleWeights(vec2 uv) {
        vec2 u = clamp(uv, 0.002, 0.998); vec4 M[10];
        for (int k = 0; k < 10; k++) M[k] = texture2D(mkAtlas, vec2((u.x + float(k % 4)) / 4.0, (u.y + float(k / 4)) / 3.0));
        for (int m = 0; m < 6; m++) { float s = 0.0; for (int k = 0; k < 10; k++) s += dot(M[k], uW[m * 10 + k]); wA[m] = clamp(s, 0.0, 1.0) * uWrinkle; }
      }`;
    const chunk = (name, from, to) => { const c = THREE.ShaderChunk[name]; if (!c.includes(from)) throw new Error('shader chunk changed: ' + name); return c.replace(from, to); };
    const mapF = chunk('map_fragment', 'vec4 sampledDiffuseColor = texture2D( map, vMapUv );',
      `wrinkleWeights(vMapUv); vec4 sampledDiffuseColor = texture2D( map, vMapUv );
       sampledDiffuseColor.rgb = mix(sampledDiffuseColor.rgb, texture2D(cm1, vMapUv).rgb, wA[0]);
       sampledDiffuseColor.rgb = mix(sampledDiffuseColor.rgb, texture2D(cm2, vMapUv).rgb, wA[1]);
       sampledDiffuseColor.rgb = mix(sampledDiffuseColor.rgb, texture2D(cm3, vMapUv).rgb, wA[2]);`);
    const nrmF = chunk('normal_fragment_maps', 'vec3 mapN = texture2D( normalMap, vNormalMapUv ).xyz * 2.0 - 1.0;',
      `vec3 nC = texture2D( normalMap, vNormalMapUv ).xyz;
       nC = mix(nC, texture2D(wm1, vNormalMapUv).xyz, wA[3]); nC = mix(nC, texture2D(wm2, vNormalMapUv).xyz, wA[4]);
       nC = mix(nC, texture2D(wm3, vNormalMapUv).xyz, wA[5]); vec3 mapN = nC * 2.0 - 1.0;`);
    const rghF = chunk('roughnessmap_fragment', 'roughnessFactor *= texelRoughness.g;', 'roughnessFactor *= texelRoughness.r;');  // MetaHuman: R
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\n' + decl)
      .replace('#include <map_fragment>', mapF).replace('#include <normal_fragment_maps>', nrmF).replace('#include <roughnessmap_fragment>', rghF);
  };
  return m;
}
const MAT = {
  body: () => new THREE.MeshStandardMaterial({ color: 0x5f3e31, roughness: 0.7 }),  // ~ mean of the head colour map: no seam at the collar
  teeth: () => new THREE.MeshStandardMaterial({ map: T_.teeth, roughness: 0.35 }),
  eye: () => {   // live gaze: the eyeball is rotated about its centre in bind space (after the morphs, before skinning)
    const m = new THREE.MeshStandardMaterial({ map: T_.eyes, roughness: 0.25 });
    const U = { uEyeR: { value: new THREE.Matrix3() }, uEyeC: { value: new THREE.Vector3() } }; m.userData.E = U;
    m.customProgramCacheKey = () => 'gazeEye';
    m.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, U);
      sh.vertexShader = 'uniform mat3 uEyeR; uniform vec3 uEyeC;\n' + sh.vertexShader
        .replace('#include <morphnormal_vertex>', '#include <morphnormal_vertex>\n objectNormal = uEyeR * objectNormal;')
        .replace('#include <morphtarget_vertex>', '#include <morphtarget_vertex>\n transformed = uEyeR * (transformed - uEyeC) + uEyeC;');
    };
    return m;
  },
  shell: () => new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: 0.06, roughness: 0.02, metalness: 0, depthWrite: false }),
  hidden: () => new THREE.MeshBasicMaterial({ visible: false }),
  lash: () => new THREE.MeshStandardMaterial({ color: 0x1a1410, alphaMap: T_.lash, transparent: true, alphaTest: 0.25, roughness: 0.7 }),
};
const pickMat = (name) => name.startsWith('head') ? 'head' : name.startsWith('teeth') ? 'teeth' : (name.startsWith('eyeLeft') || name.startsWith('eyeRight')) ? 'eye'
  : name.startsWith('eyeshell') ? 'shell' : name.startsWith('eyeEdge') ? 'hidden' : name.startsWith('eyelash') ? 'lash' : 'body';

// ---------- characters ----------
const gltf = await new GLTFLoader().loadAsync('data/boss.glb');
const CLIP = (n) => gltf.animations.find((a) => a.name === n);
if (CLIP('Walk')) CLIP('Walk').tracks = CLIP('Walk').tracks.filter((tr) => tr.name !== 'root.position');  // walk in place
const fwd0 = new THREE.Vector3(...meta.forwardGltf).normalize(); const UP = new THREE.Vector3(0, 1, 0);
const camRight = fwd0.clone().cross(UP).multiplyScalar(-1);  // camera faces the characters: its right = their left
const chars = {};
for (const [id, side, turn] of [['S1', -1, 35], ['S2', 1, -35], ['B3', 0, 0], ['B4', 0, 0]]) {   // B3/B4: listeners of the Group tab
  const root = SkeletonUtils.clone(gltf.scene); scene.add(root);
  root.position.copy(camRight.clone().multiplyScalar(side * 0.36));
  root.rotation.y = THREE.MathUtils.degToRad(turn);  // + = turn to own left (toward the partner for S1)
  const meshes = [], head = [], eyes = [];
  root.traverse((o) => {
    if (!o.isSkinnedMesh && !o.isMesh) return;
    o.castShadow = o.receiveShadow = true; o.frustumCulled = false;
    const kind = pickMat(o.material.name || ''); o.material = kind === 'head' ? headMaterial() : MAT[kind]();
    if (kind === 'head') head.push(o.material);
    if (kind === 'eye') { eyes.push(o); o.userData.isEye = true; }
    if (o.morphTargetDictionary) meshes.push(o);
  });
  const bones = {}; root.traverse((o) => { if (o.isBone) bones[o.name] = o; });
  const mixer = new THREE.AnimationMixer(root); const idle = mixer.clipAction(gltf.animations.find((a) => a.name === 'Idle') || gltf.animations[0]); idle.enabled = true; idle.play();
  idle.time = { S1: 0, S2: 4.3, B3: 2.1, B4: 6.7 }[id];  // desync the idles
  if (id[0] === 'B') root.visible = false;
  const acts = { idle };
  for (const n of ['Sit', 'Walk']) if (CLIP(n)) { const a = mixer.clipAction(CLIP(n)); a.play(); a.setEffectiveWeight(0); if (id === 'S2') a.time = CLIP(n).duration * 0.37; acts[n.toLowerCase()] = a; }
  chars[id] = { root, meshes, head, eyes, acts, act: idle, mean: null, bones, pre: [], damp: [], mixer, idle, c: meta.parts['c_' + id] ? part('c_' + id) : null, w: meta.parts['w_' + id] ? part('w_' + id) : null,
    h: meta.parts['h_' + id] ? part('h_' + id) : null, delay: { B3: 0.35, B4: 0.7 }[id] || 0, amp: 1, turn };
}

// ---------- neck skin weights (Nov 7): the fitted Boss head mesh is 100 % 'head' from mid-neck up (the MetaHuman neck
// joints were collapsed onto 'head' in the UEFN fit), so the whole upper neck moved rigidly with the skull and a turned
// / lifted head showed a hard edge where the weights jump (~5 cm above neck_01). Re-spread them along the chain:
// neck_01 -> neck_02 -> head by height along the neck, only on the neck tube (not the jaw / chin), blended out softly.
// Runs once on the shared geometry (all characters). The Unreal asset needs the same fix in its source FBX.
function fixNeckWeights(C) {
  let H = null; C.root.traverse((o) => { if (o.isSkinnedMesh && C.head.includes(o.material)) H = o; });
  if (!H || H.geometry.userData.neckFixed) return null;
  C.root.updateMatrixWorld(true);
  const B = H.skeleton.bones, ix = (n) => B.findIndex((b) => b.name === n);
  const i1 = ix('neck_01'), i2 = ix('neck_02'), i3 = ix('head'); if (i1 < 0 || i2 < 0 || i3 < 0) return null;
  const P1 = B[i1].getWorldPosition(new THREE.Vector3()), P2 = B[i2].getWorldPosition(new THREE.Vector3()), P3 = B[i3].getWorldPosition(new THREE.Vector3());
  const ax = P3.clone().sub(P1).normalize(), Ln = P3.distanceTo(P1), u2 = P2.clone().sub(P1).dot(ax) / Ln;
  const nodes = [[u2 / 2, i1], [(u2 + 1) / 2, i2], [1.05, i3]];   // segment middles: 100 % that bone
  const g = H.geometry, P = g.attributes.position, SI = g.attributes.skinIndex, SW = g.attributes.skinWeight, v = new THREE.Vector3();
  const sstep = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
  let changed = 0;
  for (let i = 0; i < P.count; i++) {
    v.fromBufferAttribute(P, i); H.applyBoneTransform(i, v); v.applyMatrix4(H.matrixWorld);
    const rel = v.clone().sub(P1), u = rel.dot(ax) / Ln, r = rel.clone().addScaledVector(ax, -rel.dot(ax)).length();
    if (u < nodes[0][0] || u > nodes[2][0]) continue;
    const f = sstep(0.078, 0.062, r) * sstep(nodes[0][0], nodes[0][0] + 0.12, u);   // neck tube only, fade in from below
    if (f <= 0.01) continue;
    const tgt = {};
    for (let k = 0; k < 2; k++) { const [ua, ba] = nodes[k], [ub, bb] = nodes[k + 1]; if (u >= ua && u <= ub) { const a = (u - ua) / (ub - ua); tgt[ba] = 1 - a; tgt[bb] = a; } }
    const w = {};
    for (let k = 0; k < 4; k++) { const b = SI.getComponent(i, k), x = SW.getComponent(i, k); if (x > 0) w[b] = (w[b] || 0) + x * (1 - f); }
    for (const [b, x] of Object.entries(tgt)) w[b] = (w[b] || 0) + x * f;
    const top = Object.entries(w).sort((a, b) => b[1] - a[1]).slice(0, 4), sum = top.reduce((a, [, x]) => a + x, 0);
    for (let k = 0; k < 4; k++) { SI.setComponent(i, k, top[k] ? +top[k][0] : 0); SW.setComponent(i, k, top[k] ? top[k][1] / sum : 0); }
    changed++;
  }
  SI.needsUpdate = SW.needsUpdate = true; g.userData.neckFixed = true;
  return changed;
}
const NECKFIX = /neckfix=1/.test(location.search) ? fixNeckWeights(chars.S1) : 0;   // REVERTED (Nov 7): it softened the jawline; original weights by default
console.log('neck weights re-spread on', NECKFIX, 'vertices');

// ---------- live gaze: eyeball geometry (centre, optical axis, head-fixed up/right) in bind space ----------
const _A = new THREE.Matrix4(), _Ai = new THREE.Matrix4(), _m4 = new THREE.Matrix4(), _q = new THREE.Quaternion();
function eyeA(E, G, out) { return out.copy(E.matrixWorld).multiply(E.bindMatrixInverse).multiply(G.bone.matrixWorld).multiply(G.boneInv).multiply(E.bindMatrix); }
for (const id in chars) {
  const C = chars[id]; C.root.updateMatrixWorld(true);
  const hq = C.bones.head.getWorldQuaternion(new THREE.Quaternion()).invert();   // face forward / up in head-bone space
  { const sk = C.eyes[0] && C.eyes[0].skeleton, bq = (n) => { const i = sk.bones.findIndex((b) => b.name === n), q = new THREE.Quaternion(); sk.boneInverses[i].clone().invert().decompose(new THREE.Vector3(), q, new THREE.Vector3()); return q; };
    if (sk) { C.relBind = bq('spine_05').invert().multiply(bq('head'));   // neutral head in chest space (bind pose)
      C.restLocal = { neck_01: bq('spine_05').invert().multiply(bq('neck_01')), neck_02: bq('neck_01').invert().multiply(bq('neck_02')), head: bq('neck_02').invert().multiply(bq('head')) }; } }
  C.headF = fwd0.clone().applyAxisAngle(UP, C.root.rotation.y).applyQuaternion(hq); C.headU = UP.clone().applyQuaternion(hq);
  for (const E of C.eyes) {
    const g = E.geometry, P = g.attributes.position, mi = E.morphTargetDictionary ? E.morphTargetDictionary.mu : undefined;
    const MU = mi !== undefined ? g.morphAttributes.position[mi] : null, rel = g.morphTargetsRelative;
    const pts = []; const c = new THREE.Vector3();
    for (let i = 0; i < P.count; i++) {
      const v = new THREE.Vector3().fromBufferAttribute(P, i);
      if (MU) { const m = new THREE.Vector3().fromBufferAttribute(MU, i); if (rel) v.add(m); else v.copy(m); }
      pts.push(v); c.add(v);
    }
    c.multiplyScalar(1 / pts.length);
    const si = g.attributes.skinIndex, sw = g.attributes.skinWeight, cnt = {};
    for (let i = 0; i < P.count; i += 7) { let bi = 0, bw = -1; for (let k = 0; k < 4; k++) if (sw.getComponent(i, k) > bw) { bw = sw.getComponent(i, k); bi = si.getComponent(i, k); } cnt[bi] = (cnt[bi] || 0) + 1; }
    const bIdx = +Object.entries(cnt).sort((a, b) => b[1] - a[1])[0][0];
    const G = { c, bone: E.skeleton.bones[bIdx], boneInv: E.skeleton.boneInverses[bIdx], yaw: 0, pitch: 0 };
    eyeA(E, G, _A); _Ai.copy(_A).invert();
    const fw = fwd0.clone().applyAxisAngle(UP, C.root.rotation.y).transformDirection(_Ai), up = UP.clone().transformDirection(_Ai);
    const pr = pts.map((v) => v.clone().sub(c).dot(fw)).sort((a, b) => b - a), cut = pr[Math.max(0, Math.floor(pr.length * 0.03))];
    const front = new THREE.Vector3(); let nf = 0; for (const v of pts) if (v.clone().sub(c).dot(fw) >= cut) { front.add(v); nf++; }
    G.f = front.multiplyScalar(1 / nf).sub(c).normalize();          // fallback optical axis: centre -> cornea cap
    const UV = g.attributes.uv;   // better: the pupil = the vertex at the centre of the eye texture (UV 0.5, 0.5)
    if (UV) { let bi = -1, bd = 1e9; for (let i = 0; i < P.count; i++) { const du = UV.getX(i) - 0.5, dv = UV.getY(i) - 0.5; if (du * du + dv * dv < bd) { bd = du * du + dv * dv; bi = i; } }
      if (bd < 1e-3) G.f = pts[bi].clone().sub(c).normalize(); }
    G.u = up.clone().addScaledVector(G.f, -up.dot(G.f)).normalize(); G.r = G.f.clone().cross(G.u).normalize();
    G.boneName = G.bone.name; E.userData.G = G; E.material.userData.E.uEyeC.value.copy(c);
  }
}

// ---------- speech-pose motions (Motion section) ----------
const POSES = loadPoses(gltf.animations.find((a) => a.name === 'Poses'));
const posers = {}; for (const id in chars) posers[id] = createPoser(chars[id], POSES);
const activeIds = () => Object.keys(chars).filter((id) => chars[id].root.visible);
// motion being edited = a pose + a [min, max] range per parameter; every preview take samples inside the ranges
const MR = { pose: 1, r: {} };
let INST = { ...DEFAULT_PARAMS };           // the current take (sampled values)
const prev = { on: false, who: 'S1', tau: 0, loop: true, lead: 0.5, tail: 0.8, mode: 'random' };
// dialogue script (word timings, pitch prominence, phrase ends, script emotions) for placing gestures on the speech
let SCRIPT = null; try { const r = await fetch('data/script.json', { cache: 'no-store' }); if (r.ok) SCRIPT = await r.json(); } catch (e) {}
let SPEECH = []; const SP = { on: true };  // preview playback

// ---------- lights (adjustable in the Light section) ----------
const center = new THREE.Vector3(0, meta.headCenterGltf[1], 0);
const hemi = new THREE.HemisphereLight(0xd6dbe6, 0x4a4033, 0.55); scene.add(hemi);
const key = new THREE.DirectionalLight(0xfff3e6, 2.6); key.target.position.copy(center); scene.add(key, key.target);
key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02;
Object.assign(key.shadow.camera, { left: -1.5, right: 1.5, top: 2.2, bottom: -2, near: 0.1, far: 8 });
const fill = new THREE.DirectionalLight(0xdfe8ff, 0.45); scene.add(fill);
const rim = new THREE.DirectionalLight(0xffffff, 1.2); scene.add(rim);
const LIGHT_DEFAULT = { exposure: 1.25, key: 2.6, keyAz: 55, keyEl: 35, keyWarm: 0.5, fill: 0.45, rim: 1.2, ambient: 0.55 };
const LIGHT = { ...LIGHT_DEFAULT };
const warm = (k) => new THREE.Color().setRGB(1, 1 - 0.12 * k, 1 - 0.3 * k);  // 0 = neutral white, 1 = warm tungsten-ish
function placeAt(light, az, el, dist) {  // azimuth from the camera-facing direction (+ = camera right), elevation above horizon
  const a = THREE.MathUtils.degToRad(az), e = THREE.MathUtils.degToRad(el);
  const dir = fwd0.clone().multiplyScalar(Math.cos(a) * Math.cos(e)).add(camRight.clone().multiplyScalar(Math.sin(a) * Math.cos(e)))
    .add(UP.clone().multiplyScalar(Math.sin(e)));
  light.position.copy(center).add(dir.multiplyScalar(dist));
}
function applyLight() {
  renderer.toneMappingExposure = LIGHT.exposure; key.intensity = LIGHT.key; key.color.copy(warm(LIGHT.keyWarm));
  placeAt(key, LIGHT.keyAz, LIGHT.keyEl, 2.6); placeAt(fill, LIGHT.keyAz - 110, 10, 2.6); placeAt(rim, 180 - LIGHT.keyAz * 0.3, 30, 2.6);
  fill.intensity = LIGHT.fill; rim.intensity = LIGHT.rim; hemi.intensity = LIGHT.ambient;
}

// ---------- cameras ----------
const headPos = (id) => { const p = new THREE.Vector3(); chars[id].bones.head.getWorldPosition(p); return p; };
let CURCAM = 'two';
function setCam(kind) {
  CURCAM = kind;
  scene.updateMatrixWorld(true);
  const ids = Object.keys(chars).filter((id) => chars[id].root.visible);
  const mid = ids.reduce((acc, id) => acc.add(headPos(id)), new THREE.Vector3()).multiplyScalar(1 / ids.length);
  let target = mid.clone(), pos;
  if (kind === 'two') {  // heads in the upper third, shifted left of the control panel (a group: everyone)
    const wide = ids.length > 2 ? 1.2 + SCEN.spread * 1.6 : 0;
    target = mid.clone().add(UP.clone().multiplyScalar(-0.12 - wide * 0.05)).add(camRight.clone().multiplyScalar(0.14 + wide * 0.08));
    pos = target.clone().add(fwd0.clone().multiplyScalar(2.4 + wide)).add(UP.clone().multiplyScalar(0.12 + wide * 0.1));
  } else if (kind === 'hands') {  // the seller's hands (fingers come from the idle)
    const hl = new THREE.Vector3(), hr = new THREE.Vector3(); chars.S1.bones.hand_l.getWorldPosition(hl); chars.S1.bones.hand_r.getWorldPosition(hr);
    target = hl.add(hr).multiplyScalar(0.5); const f = fwd0.clone().applyAxisAngle(UP, chars.S1.root.rotation.y);
    const cr = f.clone().cross(UP).multiplyScalar(-0.12); target.add(cr);  // keep both hands left of the panel
    pos = target.clone().add(f.multiplyScalar(0.85)).add(UP.clone().multiplyScalar(0.12));
  }
  else if (kind === 'full') { target = new THREE.Vector3(0, 0.95, 0); pos = target.clone().add(fwd0.clone().multiplyScalar(5.2)).add(UP.clone().multiplyScalar(0.3)); }
  else {  // over-the-shoulder-ish close-up from the partner's side
    const other = kind === 'S1' ? 'S2' : 'S1'; target = headPos(kind);
    const dir = headPos(other).sub(target).setY(0).normalize().add(fwd0.clone().multiplyScalar(0.9)).normalize();
    pos = target.clone().add(dir.multiplyScalar(0.95)).add(UP.clone().multiplyScalar(0.02));
  }
  camera.position.copy(pos); controls.target.copy(target); controls.update();
  document.querySelectorAll('[data-cam]').forEach((b) => b.classList.toggle('on', b.dataset.cam === kind));
}

// ---------- animation ----------
const L = { face: true, wrinkle: true, head: true, body: true };
const SPLIT = [['neck_01', 0.3], ['neck_02', 0.3], ['head', 0.4]];
const qa = new THREE.Quaternion(), qb = new THREE.Quaternion(), qc = new THREE.Quaternion(), qw = new THREE.Quaternion(), qp = new THREE.Quaternion();
let EMO = 1.6;  // emotion gain (approved 1.6); blends the two nearest baked levels
function levelAt(g) {
  if (LEVELS.length < 2) return [0, 0, 0];
  let i = 0; while (i < LEVELS.length - 2 && g > LEVELS[i + 1]) i++;
  const b = Math.min(Math.max((g - LEVELS[i]) / (LEVELS[i + 1] - LEVELS[i]), 0), 1); return [i, i + 1, b];
}
let LV = levelAt(EMO);
function sample(p, f0, f1, a, i) {
  if (p.lv === 1) return p.a[f0 * p.w + i] * (1 - a) + p.a[f1 * p.w + i] * a;
  const [l0, l1, b] = LV, o0 = l0 * p.fs, o1 = l1 * p.fs;
  const v0 = p.a[o0 + f0 * p.w + i] * (1 - a) + p.a[o0 + f1 * p.w + i] * a, v1 = p.a[o1 + f0 * p.w + i] * (1 - a) + p.a[o1 + f1 * p.w + i] * a;
  return v0 * (1 - b) + v1 * b;
}
const frameAt = (tt) => { const fl = Math.min(Math.max(tt * FPS, 0), NF - 1), f0 = Math.floor(fl); return [f0, Math.min(f0 + 1, NF - 1), fl - f0]; };
// a bystander (Group tab) has no face track of his own: he wears the face of whichever speaker is LISTENING at that
// moment (closed mouth, blinks, listener reactions), a little later (B3 0.35 s, B4 0.7 s), neutral between turns
function listenerMix(tt) {
  const [g0, g1, ga] = frameAt(tt), fi = Math.round(tt * FPS);
  const w1 = LW.S1[Math.min(NF - 1, Math.max(0, fi))] || 0, w2 = LW.S2[Math.min(NF - 1, Math.max(0, fi))] || 0;
  return { g0, g1, ga, src: [[chars.S1, w1], [chars.S2, w2]] };
}
const mixVal = (M, key, i) => M.src.reduce((acc, [S, w]) => acc + (w > 1e-3 ? w * sample(S[key], M.g0, M.g1, M.ga, i) : 0), 0);
function poseAt(t) {
  const fl = Math.min(Math.max(t * FPS, 0), NF - 1), f0 = Math.floor(fl), f1 = Math.min(f0 + 1, NF - 1), a = fl - f0;
  for (const id of activeIds()) {
    const C = chars[id], M = C.c ? null : listenerMix(t - C.delay);
    const val = (key, i) => (M ? mixVal(M, key, i) : sample(C[key], f0, f1, a, i));
    // face morphs: mu + sum c_k pc_k
    for (const m of C.meshes) {
      const d = m.morphTargetDictionary, inf = m.morphTargetInfluences;
      inf[d.mu] = L.face ? 1 : 0;
      const live = GZ.on && m.userData.isEye;   // live gaze replaces the eyeballs' baked gaze
      for (let k = 0; k < K; k++) inf[d['pc' + k]] = L.face && !live ? val('c', k) : 0;
    }
    // wrinkle weights per map/pack/channel
    for (const mat of C.head) {
      const uW = mat.userData.U.uW.value; uW.forEach((v) => v.set(0, 0, 0, 0));
      for (let i = 0; i < slot.length; i++) { const [mp, pk, ch] = slot[i]; if (mp < 0) continue; uW[mp * 10 + pk].setComponent(ch, val('w', i)); }
      mat.userData.U.uWrinkle.value = L.wrinkle ? 1 : 0;
    }
    C.yaw = val('h', 0); C.pitch = val('h', 1); C.roll = val('h', 2);
  }
}
// the head turns about its own neck axis (half the neck_01->head line, half the head's up), not the world vertical:
// on a slumped / bent-forward neck a world-vertical turn swings the head sideways like a crane (user, Nov 7)
function neckFrame(C) {
  const n0 = C.bones.neck_01.getWorldPosition(new THREE.Vector3()), h0 = C.bones.head.getWorldPosition(new THREE.Vector3());
  const hq = C.bones.head.getWorldQuaternion(new THREE.Quaternion());
  const A = h0.sub(n0).normalize().add(C.headU.clone().applyQuaternion(hq)).normalize();
  const hf = C.headF.clone().applyQuaternion(hq);
  const F = hf.clone().addScaledVector(A, -hf.dot(A)).normalize(), R = F.clone().cross(A).normalize();
  return (C.nf = { A, F, R, hf });
}
function applyHead(C) {
  C.pre.length = 0;
  const gy = GZ.on ? C.gYaw || 0 : 0, gp = GZ.on ? C.gPitch || 0 : 0;
  if (!L.head && !gy && !gp) return;
  const by = L.head ? C.yaw : 0, bp = L.head ? C.pitch : 0, br = L.head ? C.roll : 0;
  const chain = GZ.on && (Math.abs(C.sYaw || 0) > 0.05 || Math.abs(C.sPitch || 0) > 0.05)
    ? [['spine_04', 0, 1], ['spine_05', 0, 1], ...SPLIT.map(([n, f]) => [n, f, 0])] : SPLIT.map(([n, f]) => [n, f, 0]);
  const fwd = fwd0.clone().applyAxisAngle(UP, C.root.rotation.y); const right = fwd.clone().cross(UP);
  const CHILD = { neck_01: 'neck_02', neck_02: 'head' }, _ax = new THREE.Vector3(), _p0 = new THREE.Vector3(), _p1 = new THREE.Vector3();
  // head roll (sideways tilt) before the turn: the twist along a forward-bent neck adds roll, which we take back out below
  const H = C.bones.head, rollOf = () => {
    const q = H.getWorldQuaternion(new THREE.Quaternion()), F = C.headF.clone().applyQuaternion(q), U = C.headU.clone().applyQuaternion(q);
    const Rr = F.clone().cross(U), Uf = UP.clone().addScaledVector(F, -F.dot(UP)).normalize(), X = Uf.clone().cross(F);
    return [Math.atan2(Rr.dot(Uf), Rr.dot(X)), F];
  };
  H.updateWorldMatrix(true, false);
  const CH = C.bones.spine_05, Hb = H.getWorldQuaternion(new THREE.Quaternion()), Cb = CH.getWorldQuaternion(new THREE.Quaternion());   // neutral (pre-turn) head vs chest
  for (const [name, frac, spine] of chain) {
    const b = C.bones[name]; if (!b) continue;
    C.pre.push([b, b.quaternion.clone()]);
    const gfy = GSPLIT_Y[name] || 0, gfp = GSPLIT_P[name] || 0;   // the baked head motion keeps its own split
    const yy = spine ? C.sYaw * gfy : by * frac + gy * gfy, pp = spine ? C.sPitch * gfp : bp * frac + gp * gfp, rr = spine ? 0 : br * frac;
    b.updateWorldMatrix(true, false); b.getWorldQuaternion(qw); b.parent.getWorldQuaternion(qp);
    // turn axis: the neck bone's own length (head: its up), 60 %, blended with the vertical: a bent neck twists along
    // itself instead of swinging the head sideways (user, Nov 7)
    _ax.copy(UP);
    if (!spine) {
      if (CHILD[name] && C.bones[CHILD[name]]) { b.getWorldPosition(_p0); C.bones[CHILD[name]].getWorldPosition(_p1); _p1.sub(_p0).normalize(); }
      else _p1.copy(C.headU).applyQuaternion(qw);
      if (_p1.dot(UP) < 0) _p1.negate();
      const tw = CHILD[name] ? 0.6 : GZ.headTwist;   // the head itself: how much it turns about its own up (tilts the face) vs the vertical
      _ax.multiplyScalar(1 - tw).addScaledVector(_p1, tw).normalize();
    }
    qa.setFromAxisAngle(_ax, THREE.MathUtils.degToRad(yy));
    qb.setFromAxisAngle(right, THREE.MathUtils.degToRad(pp));
    qc.setFromAxisAngle(fwd, THREE.MathUtils.degToRad(rr));
    const R = qa.multiply(qb).multiply(qc);
    b.quaternion.copy(qp.invert().multiply(R.multiply(qw)));
    b.updateMatrixWorld(true);
  }
  if (GZ.rollCut > 0 && C.restLocal) {
    // head ROLL (ear toward shoulder) in parent space (user, Nov 7, shown with the gizmo's green ring): each neck/head bone's
    // rotation from its rest, in its own local frame; local Y is the face axis on this rig (forward = -Y, up = +X), so the
    // twist about Y is that bone's roll. The chain's total roll is cut by rollCut, taken out at the head.
    let roll = 0;
    for (const n of ['neck_01', 'neck_02', 'head']) {
      const b = C.bones[n], r = C.restLocal[n]; if (!b || !r) continue;
      const D = r.clone().invert().multiply(b.quaternion); let tw = 2 * Math.atan2(D.y, D.w); roll += Math.atan2(Math.sin(tw), Math.cos(tw));
    }
    if (Math.abs(roll) > 1e-4) { H.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), -GZ.rollCut * roll)); H.updateMatrixWorld(true); }
  }
}

// ---------- audio (8 line files scheduled on the scene timeline) ----------
const actx = new AudioContext();
const buffers = await Promise.all(meta.lines.map(async (l) => actx.decodeAudioData(await (await fetch(l.audio)).arrayBuffer())));
let sources = [];
function startAudio(t) {
  stopAudio();
  meta.lines.forEach((l, i) => {
    if (l.start + l.dur <= t) return;
    const s = actx.createBufferSource(); s.buffer = buffers[i]; s.connect(actx.destination);
    const delay = Math.max(0, l.start - t), offset = Math.max(0, t - l.start);
    s.start(actx.currentTime + delay, offset); sources.push(s);
  });
}
function stopAudio() { sources.forEach((s) => { try { s.stop(); } catch (e) {} }); sources = []; }

// ---------- transport ----------
let t = 0, playing = false, speed = 1, clockRef = 0, tRef = 0;
const clock = new THREE.Clock();
function play() {
  if (t >= T - 0.01) t = 0; stopPreview();
  playing = true; $('play').textContent = '❚❚'; tRef = t; clockRef = performance.now() / 1000;
  if (speed === 1) { actx.resume(); startAudio(t); clockRef = null; tRef = t - 0; audioRef = actx.currentTime; }
}
let audioRef = 0;
function pause() { playing = false; $('play').textContent = '▶'; stopAudio(); }
$('play').onclick = () => (playing ? pause() : play());
addEventListener('keydown', (e) => { if (e.code === 'Space') { e.preventDefault(); playing ? pause() : play(); } });
// arrows: a tap steps one frame, holding scrubs continuously (starts after 0.12 s, no OS key-repeat delay), left = back
const ARROW = { dir: 0, since: 0 };
addEventListener('keydown', (e) => {
  if (e.code !== 'ArrowLeft' && e.code !== 'ArrowRight') return;
  if (e.target && (e.target.type === 'text' || e.target.tagName === 'TEXTAREA')) return;
  e.preventDefault(); if (e.repeat) return;
  if (playing) pause();
  ARROW.dir = e.code === 'ArrowLeft' ? -1 : 1; ARROW.since = performance.now();
  t = Math.min(T, Math.max(0, t + ARROW.dir / FPS));
});
addEventListener('keyup', (e) => { if (e.code === 'ArrowLeft' || e.code === 'ArrowRight') ARROW.dir = 0; });
addEventListener('blur', () => { ARROW.dir = 0; });
$('scrub').oninput = (e) => { t = (+e.target.value / 1000) * T; if (playing) play(); };
document.querySelectorAll('[data-speed]').forEach((b) => b.onclick = () => {
  speed = +b.dataset.speed; document.querySelectorAll('[data-speed]').forEach((x) => x.classList.toggle('on', x === b)); if (playing) play();
});
document.querySelectorAll('[data-cam]').forEach((b) => b.onclick = () => setCam(b.dataset.cam));
for (const [id, k] of [['lyFace', 'face'], ['lyWrinkle', 'wrinkle'], ['lyHead', 'head'], ['lyBody', 'body']]) $(id).onchange = (e) => { L[k] = e.target.checked; };

// ---- per-viewer UI memory (best effort: storage can be unavailable) ----
// Settings persist in settings.json next to the lab (written by server.py), so they survive browser resets, work in any
// browser window and Claude can read them. localStorage is only a fallback if the file can't be read.
let SETTINGS = {};
try { const r = await fetch('settings', { cache: 'no-store' }); if (r.ok) SETTINGS = await r.json(); } catch (e) {}
if (!Object.keys(SETTINGS).length) try {
  SETTINGS = JSON.parse(localStorage.getItem('dlab.settings') || '{}');
  // one-time migration from the first version, which kept each setting under its own browser key
  for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i);
    if (k.startsWith('dlab.') && k !== 'dlab.settings' && !(k.slice(5) in SETTINGS)) SETTINGS[k.slice(5)] = JSON.parse(localStorage.getItem(k)); }
} catch (e) {}
let saveTimer = null;
function saveSettings() {
  try { localStorage.setItem('dlab.settings', JSON.stringify(SETTINGS)); } catch (e) {}
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => fetch('settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(SETTINGS) })
    .then((r) => { $('saveState').textContent = r.ok ? 'Settings saved' : 'Settings NOT saved'; }).catch(() => { $('saveState').textContent = 'Settings NOT saved (server)'; }), 300);
}
const store = { get(k, d) { return k in SETTINGS ? JSON.parse(JSON.stringify(SETTINGS[k])) : d; },
  set(k, v) { SETTINGS[k] = JSON.parse(JSON.stringify(v)); saveSettings(); } };
// layers + playback speed persist too
Object.assign(L, store.get('layers', {}));
for (const [id, k] of [['lyFace', 'face'], ['lyWrinkle', 'wrinkle'], ['lyHead', 'head'], ['lyBody', 'body']]) {
  $(id).checked = L[k]; $(id).addEventListener('change', () => store.set('layers', L));
}
speed = store.get('speed', 1); document.querySelectorAll('[data-speed]').forEach((x) => {
  x.classList.toggle('on', +x.dataset.speed === speed); x.addEventListener('click', () => store.set('speed', speed));
});
// panel width: drag its left edge (saved with the settings)
function setPanelW(w) { w = Math.round(Math.min(Math.max(w, 220), Math.max(240, innerWidth * 0.8))); document.documentElement.style.setProperty('--panelW', w + 'px'); return w; }
setPanelW(store.get('panelW', 240));
{ const grip = $('panelGrip'); let drag = false;
  grip.addEventListener('pointerdown', (e) => { drag = true; grip.classList.add('drag'); grip.setPointerCapture(e.pointerId); e.preventDefault(); });
  grip.addEventListener('pointermove', (e) => { if (drag) setPanelW(innerWidth - 10 - e.clientX); });
  grip.addEventListener('pointerup', (e) => { if (!drag) return; drag = false; grip.classList.remove('drag'); store.set('panelW', setPanelW(innerWidth - 10 - e.clientX)); drawCurve(prev.on ? prev.tau - prev.lead : null); });
}
document.querySelectorAll('details[data-sec]').forEach((d) => {
  d.open = store.get('open.' + d.dataset.sec, d.open); d.addEventListener('toggle', () => store.set('open.' + d.dataset.sec, d.open));
});

// ---- listener nods: amplify only the quick pitch movements of the head while a character listens ----
// pitch = slow drift (zero-phase low-pass, ~0.8 s) + nods (the rest); only the nod part is scaled, only while listening
const NOD = { gain: store.get('nodGain', 1) };
for (const id in chars) { const C = chars[id]; if (C.h) C.hOrig = Float32Array.from(C.h.a); }
function listenWeight(id) {  // 1 while the partner speaks, smooth 0.6 s ramps at turn changes
  const n = NF, w = new Float32Array(n);
  for (let f = 0; f < n; f++) { const t = f / FPS; let v = 0;
    for (const l of meta.lines) if (l.speaker !== id) { const a = Math.min(1, Math.max(0, (t - l.start + 0.3) / 0.6)), b = Math.min(1, Math.max(0, (l.start + l.dur + 0.3 - t) / 0.6)); v = Math.max(v, Math.min(a, b)); }
    w[f] = v * v * (3 - 2 * v); }
  return w;
}
const LW = {}; for (const id in chars) LW[id] = listenWeight(id);
function applyNodGain() {
  const k = Math.exp(-1 / (FPS * 0.8));
  for (const id in chars) {
    if (!chars[id].h) continue;
    const C = chars[id], W = C.h.w, n = NF, p = new Float32Array(n);
    for (let f = 0; f < n; f++) p[f] = C.hOrig[f * W + 1];
    const base = Float32Array.from(p);
    for (let pass = 0; pass < 2; pass++) { let acc = base[0]; for (let f = 0; f < n; f++) { acc = k * acc + (1 - k) * base[f]; base[f] = acc; } acc = base[n - 1]; for (let f = n - 1; f >= 0; f--) { acc = k * acc + (1 - k) * base[f]; base[f] = acc; } }
    for (let f = 0; f < n; f++) C.h.a[f * W + 1] = p[f] + (NOD.gain - 1) * (p[f] - base[f]) * LW[id][f];
  }
  $('nodVal').textContent = NOD.gain.toFixed(2) + '×';
}
$('nodGain').value = NOD.gain; $('nodGain').oninput = (e) => { NOD.gain = +e.target.value; applyNodGain(); store.set('nodGain', NOD.gain); };
applyNodGain();

// ---- idle sway: the game idle's motion (breathing, weight shifts) scaled around its own average pose; 1 = as authored ----
function clipMean(clip) {
  if (!clip) return null; const m = {}, n = Math.round(clip.duration * 30) + 1;
  for (const tr of clip.tracks) {
    const [bone, prop] = tr.name.split('.'); if (bone.startsWith('ik_')) continue;
    const ip = tr.createInterpolant();
    if (prop === 'quaternion') {   // average rotation (sign-aligned sum, normalised)
      const r = Array.from(ip.evaluate(0)), sum = [0, 0, 0, 0];
      for (let i = 0; i < n; i++) { const v = ip.evaluate(i / 30); const d = v[0] * r[0] + v[1] * r[1] + v[2] * r[2] + v[3] * r[3] < 0 ? -1 : 1; for (let k = 0; k < 4; k++) sum[k] += d * v[k]; }
      (m[bone] ||= {}).q = new THREE.Quaternion(...sum).normalize();
    } else if (prop === 'position') {
      const sum = [0, 0, 0]; for (let i = 0; i < n; i++) { const v = ip.evaluate(i / 30); for (let k = 0; k < 3; k++) sum[k] += v[k] / n; }
      (m[bone] ||= {}).p = new THREE.Vector3(...sum);
    }
  }
  return m;
}
const MEANS = { idle: clipMean(CLIP('Idle') || gltf.animations[0]), sit: clipMean(CLIP('Sit')) };
for (const id in chars) chars[id].mean = MEANS.idle;
// separate amounts while speaking / listening, cross-faded with the listen weight (smooth 0.6 s ramps at turn changes)
const IDLE = { spk: store.get('idleSwaySpk', store.get('idleSway', 0.5)), lst: store.get('idleSwayLst', store.get('idleSway', 0.5)) };
function swayFor(id, time) { const w = LW[id][Math.min(NF - 1, Math.max(0, Math.round(time * FPS)))]; return IDLE.spk + (IDLE.lst - IDLE.spk) * w; }
function dampIdle(C, sway) {   // after the mixer: pull every idle bone toward its average by (1 - sway); undone at the next frame
  C.damp.length = 0; const k = 1 - sway; if (k <= 1e-4) return;
  if (!C.mean) return;   // walking: no damping
  for (const [name, e] of Object.entries(C.mean)) {
    const b = C.bones[name]; if (!b) continue;
    C.damp.push([b, b.quaternion.clone(), b.position.clone()]);
    if (e.q) b.quaternion.slerp(e.q, k);
    if (e.p) b.position.lerp(e.p, k);
  }
}
for (const [key, el, out] of [['spk', 'idleSwaySpk', 'swaySpkVal'], ['lst', 'idleSwayLst', 'swayLstVal']]) {
  const show = () => { $(out).textContent = Math.round(IDLE[key] * 100) + '%'; };
  $(el).value = IDLE[key]; show();
  $(el).oninput = (e) => { IDLE[key] = +e.target.value; show(); store.set(el, IDLE[key]); };
}

// ---------- scenarios: Standing / Walk / Sit (big tabs), live layout + live gaze ----------
const rad = THREE.MathUtils.degToRad, deg = THREE.MathUtils.radToDeg, clamp = THREE.MathUtils.clamp;
const SCEN = { kind: store.get('scen', 'stand'), open: store.get('scOpen', 110), dist: store.get('scDist', 0.72), sitAng: store.get('scSitAng2', 75),
  sitDist: store.get('scSitDist', 1.0), gap: store.get('scGap', 0.75), people: store.get('scPeople', 4), spread: store.get('scSpread', 0.8),
  sitGest: store.get('scSitGest', 0.5) };
const GZ = { on: store.get('gazeOn', true), relief: store.get('neckBreaks', true), rollCut: store.get('rollCut', 0.78), headTwist: 0.6, plan: null };   // 0.78 = what the user dialled in with the gizmo (Nov 7)
// how much of a gaze turn the head takes (the eyes do the rest), per scenario; limits in degrees
const HF = { stand: { y: 0.5, p: 0.5 }, sit: { y: 0.5, p: 0.55 }, walk: { y: 0.7, p: 0.5 }, group: { y: 0.55, p: 0.5 } };
const EYE = { yaw: 30, up: 22, down: 26 };
const NECK = { yaw: 50, up: 28, down: 35 }, SPINE = { yaw: 20, up: 10, down: 15 };   // comfortable ranges (deg)
const NECK_UP = { sit: 40 }, NECK_YAW = { sit: 65 }, SPINE_UP = { sit: 18 };   // sitting: more room, the chest lifts more, the neck less
// gaze turn split: yaw over the neck + head; pitch mostly from the lower neck so the neck straightens instead of the head
// folding back on a bent neck (user, Nov 6: "rotate like the green line")
const GSPLIT_Y = { spine_04: 0.5, spine_05: 0.5, neck_01: 0.36, neck_02: 0.34, head: 0.3 };
const GSPLIT_P = { spine_04: 0.5, spine_05: 0.5, neck_01: 0.38, neck_02: 0.34, head: 0.28 };   // lower neck less than before: 0.52 made a long, straight 'giraffe' neck (Nov 7)
const stool = new THREE.Mesh(new THREE.BoxGeometry(0.42, 1, 0.42), new THREE.MeshStandardMaterial({ color: 0x6b4a2f, roughness: 0.8 }));
stool.castShadow = stool.receiveShadow = true; stool.visible = false; scene.add(stool);
let stoolPending = 0, camPending = 0;
function faceTo(C, d) { const b = d.clone().setY(0).normalize(), a = fwd0; C.root.rotation.y = Math.atan2(a.z * b.x - a.x * b.z, a.dot(b)); }
function layout() {
  const k = SCEN.kind, cr = camRight, f = fwd0, A = chars.S1, B = chars.S2;
  if (k === 'stand') {   // opening 0 = face to face; each turns half the opening toward the camera
    const h = rad(SCEN.open / 2);
    A.root.position.copy(cr).multiplyScalar(-SCEN.dist / 2); B.root.position.copy(cr).multiplyScalar(SCEN.dist / 2);
    faceTo(A, cr.clone().multiplyScalar(Math.cos(h)).addScaledVector(f, Math.sin(h)));
    faceTo(B, cr.clone().multiplyScalar(-Math.cos(h)).addScaledVector(f, Math.sin(h)));
  } else if (k === 'sit') {   // the Seller sits facing camera-right; the Customer stands around him at the slider angle, facing him
    const f1 = f.clone().applyAxisAngle(UP, rad(35)), p1 = cr.clone().multiplyScalar(-0.4);   // seated one: 3/4 to the camera
    A.root.position.copy(p1); faceTo(A, f1);
    const dir = f1.clone().applyAxisAngle(UP, rad(SCEN.sitAng));   // 0 = right in front of him, + = round toward camera right
    B.root.position.copy(p1).addScaledVector(dir, SCEN.sitDist); faceTo(B, dir.clone().negate());
  } else if (k === 'group') {   // a horseshoe open to the camera, everyone facing its centre
    const ctr = f.clone().multiplyScalar(-0.35), R = SCEN.spread, four = SCEN.people >= 4;
    const ang = four ? { S1: 205, S2: 155, B3: 268, B4: 92 } : { S1: 215, S2: 145, B3: 270 };   // deg from the camera direction
    for (const [id, a] of Object.entries(ang)) {
      const C = chars[id], p = ctr.clone().add(f.clone().applyAxisAngle(UP, rad(a)).multiplyScalar(R));
      C.root.position.copy(p); faceTo(C, ctr.clone().sub(p));
    }
  } else {   // walking side by side (in place), toward camera-right
    const w = f.clone().applyAxisAngle(UP, rad(30)), side = w.clone().applyAxisAngle(UP, rad(90));
    A.root.position.copy(side).multiplyScalar(-SCEN.gap / 2); B.root.position.copy(side).multiplyScalar(SCEN.gap / 2);
    faceTo(A, w); faceTo(B, w);
  }
  for (const id in chars) chars[id].root.position.y = 0;
  scene.updateMatrixWorld(true); if (k === 'sit') stoolPending = 2;
}
function placeStool() {   // seat top just under the hips of the sitting clip
  const S = chars.S1.bones, a = new THREE.Vector3(), b = new THREE.Vector3(), pv = new THREE.Vector3();
  if (!S.thigh_l || !S.thigh_r) return; S.thigh_l.getWorldPosition(a); S.thigh_r.getWorldPosition(b); S.pelvis.getWorldPosition(pv);
  const top = (a.y + b.y) / 2 - 0.1; if (top < 0.25) { stool.visible = false; return; }   // ground sitting: no stool
  const back = fwd0.clone().applyAxisAngle(UP, chars.S1.root.rotation.y).multiplyScalar(-0.04);
  stool.scale.y = top; stool.position.set(pv.x + back.x, top / 2, pv.z + back.z); stool.rotation.y = chars.S1.root.rotation.y; stool.visible = true;
}
function setScenario(kind) {
  for (const id in chars) { chars[id].fb = null; chars[id].hs = null; }   // gaze loop state starts fresh in a new layout
  if (!['stand', 'walk', 'sit', 'group'].includes(kind)) kind = 'stand';
  if (kind === 'walk' && !chars.S1.acts.walk) kind = 'stand'; if (kind === 'sit' && !chars.S1.acts.sit) kind = 'stand';
  SCEN.kind = kind; store.set('scen', kind);
  for (const id in chars) {
    const C = chars[id], want = kind === 'walk' ? 'walk' : kind === 'sit' && id === 'S1' ? 'sit' : 'idle';
    C.act = C.acts[want] || C.acts.idle; C.mean = want === 'walk' ? null : MEANS[want] || MEANS.idle;
    C.root.visible = id[0] === 'S' || (kind === 'group' && (id === 'B3' || SCEN.people >= 4));
    C.amp = kind === 'sit' && id === 'S1' ? SCEN.sitGest : 1;   // seated gesture amplitude (gestures only)
  }
  stool.visible = false; layout();
  GZ.plan = SCRIPT ? planGaze(SCRIPT, kind, T, { relief: GZ.relief, ids: activeIds() }) : null; camPending = 2;
  document.querySelectorAll('[data-scen]').forEach((b) => b.classList.toggle('on', b.dataset.scen === kind));
  document.querySelectorAll('#scenCtl [data-for]').forEach((el) => { el.style.display = el.dataset.for === kind ? '' : 'none'; });
  if (!chars.S1.acts.sit) $('scenNote').textContent = 'Sit / Walk clips not in this build yet.';
}
document.querySelectorAll('[data-scen]').forEach((b) => b.onclick = () => setScenario(b.dataset.scen));
for (const [el, key, fmt] of [['scOpen', 'open', (v) => Math.round(v) + '°'], ['scDist', 'dist', (v) => v.toFixed(2) + ' m'], ['scSitAng', 'sitAng', (v) => Math.round(v) + '°'],
  ['scSitDist', 'sitDist', (v) => v.toFixed(2) + ' m'], ['scGap', 'gap', (v) => v.toFixed(2) + ' m'], ['scSpread', 'spread', (v) => v.toFixed(2) + ' m'],
  ['scPeople', 'people', (v) => Math.round(v) + ''], ['scSitGest', 'sitGest', (v) => Math.round(v * 100) + '%']]) {
  const out = $(el + 'V'), show = () => { out.textContent = fmt(SCEN[key]); }, skey = { scSitAng: 'scSitAng2' }[el] || el;
  $(el).value = SCEN[key]; show();
  $(el).oninput = (e) => { SCEN[key] = el === 'scPeople' ? Math.round(+e.target.value) : +e.target.value; show(); store.set(skey, SCEN[key]);
    if (el === 'scPeople') setScenario(SCEN.kind); else if (el === 'scSitGest') { if (SCEN.kind === 'sit') chars.S1.amp = SCEN.sitGest; } else layout(); };
}
{ const show = () => { $('rollCutV').textContent = Math.round(GZ.rollCut * 100) + '%'; };
  $('rollCut').value = GZ.rollCut; show(); $('rollCut').oninput = (e) => { GZ.rollCut = +e.target.value; show(); store.set('rollCut', GZ.rollCut); }; }
$('lyGaze').checked = GZ.on; $('lyGaze').onchange = (e) => { GZ.on = e.target.checked; store.set('gazeOn', GZ.on); };
$('lyNeck').checked = GZ.relief; $('lyNeck').onchange = (e) => {   // neck breaks: relief looks + relaxing a long-held turned head
  GZ.relief = e.target.checked; store.set('neckBreaks', GZ.relief); GZ.plan = SCRIPT ? planGaze(SCRIPT, SCEN.kind, T, { relief: GZ.relief, ids: activeIds() }) : null; };


// gaze controller: target from the plan, head takes part of the turn (critically damped spring), eyes aim at the target
const _v1 = new THREE.Vector3(), _v2 = new THREE.Vector3();
function gazeHead(id, dt) {
  const C = chars[id]; neckFrame(C);
  if (!GZ.on || !GZ.plan || !GZ.plan[id]) { C.gYaw = C.gPitch = 0; C.gTarget = null; return; }
  const g = gazeAt(GZ.plan[id], t); C.gz = g;
  // who: the planned person, else the partner (speakers) / the current or last speaker (bystanders)
  let who = g.who && chars[g.who] && chars[g.who].root.visible ? g.who : null;
  if (!who) { if (id === 'S1' || id === 'S2') who = id === 'S1' ? 'S2' : 'S1';
    else { let last = 'S1'; for (const l of meta.lines) if (l.start <= t + 0.05) last = l.speaker; who = last; } }
  const O = chars[who]; C.gWho = who;
  const eye = C.eyesW || headPos(id), pe = O.eyesW || headPos(who);
  const fb = fwd0.clone().applyAxisAngle(UP, C.root.rotation.y);
  // the animated head's own direction (body clip + gestures): "neutral neck"; angles are measured from it
  const hf = C.nf.hf, hh = hf.clone().setY(0);
  const P = pe.clone().sub(eye), dist = P.length();
  let d;
  if (g.kind === 'partner' || g.kind === 'soft' || g.kind === 'avert') d = P.clone();
  else if (g.kind === 'rest') d = hf.clone().multiplyScalar(dist);
  else if (g.kind === 'between') d = hf.clone().lerp(P.clone().normalize(), g.b).normalize().multiplyScalar(dist);
  else { d = fb.clone().multiplyScalar(6); d.y = -0.7; }   // walking: the path ahead
  if (g.kind === 'avert' || g.kind === 'scan' || g.kind === 'rest') {
    d.applyAxisAngle(UP, rad(g.yaw)); const ax = d.clone().cross(UP).normalize(); d.applyAxisAngle(ax, rad(g.pitch));
  }
  C.gTarget = eye.clone().add(d);
  const hor = d.clone().setY(0), gY = deg(Math.atan2(hh.z * hor.x - hh.x * hor.z, hh.dot(hor)));
  const gP = deg(Math.atan2(d.y, hor.length())) - deg(Math.atan2(hf.y, hh.length()));
  const H = HF[SCEN.kind];
  // neck fatigue: holding a strongly turned head on the partner relaxes it after ~1.5 s (eyes keep the partner)
  const strain = clamp((Math.hypot(gY * H.y, gP * H.p) - 18) / 22, 0, 1);
  C.onP = g.kind === 'partner' && C.lastKind === 'partner' ? (C.onP || 0) + dt : 0; C.lastKind = g.kind;   // continuous hold
  const held = clamp((C.onP - 1.5) / 2.5, 0, 1);
  const k = g.hf ?? 1;   // (the automatic neck relaxing on long holds is off: neck breaks are only the speaker's planned ones)
  // head share (k < 1: looking from the corner of the eyes, neck relaxed); pushed up when the eyes alone can't reach,
  // except in 'soft' / 'rest' where eyes at their limit is the point
  let hy = H.y * k * gY, hp = H.p * k * gP;
  const reach = g.kind !== 'soft' && g.kind !== 'rest' && k > 0.9;
  if (reach) {
    if (Math.abs(gY - hy) > EYE.yaw - 2) hy = gY - Math.sign(gY) * (EYE.yaw - 2);
    if (gP - hp > EYE.up - 2) hp = gP - (EYE.up - 2); if (gP - hp < -(EYE.down - 2)) hp = gP + (EYE.down - 2);
  }
  // closed loop: what the eyes still could not reach last frame goes to the head / torso (only when reaching)
  const F = (C.fb ||= { y: 0, p: 0 }), ex = C.eyeEx || [0, 0], h0 = Math.min(dt, 0.05);
  // eye yaw is + to the right, head yaw + to the left
  for (const [kk, e] of [['y', -ex[0]], ['p', ex[1]]]) { F[kk] = reach && Math.abs(e) > 0.3 ? clamp(F[kk] + e * h0 * 4, -30, 30) : F[kk] * (1 - h0 * 3); }
  hy += F.y; hp += F.p;
  // healthy limits: the neck turns up to NECK, the upper back adds a little beyond that, the rest is not reached
  const nUp = NECK_UP[SCEN.kind] ?? NECK.up, nY = NECK_YAW[SCEN.kind] ?? NECK.yaw;
  const sy = clamp(hy - clamp(hy, -nY, nY), -SPINE.yaw, SPINE.yaw), sp = clamp(hp - clamp(hp, -NECK.down, nUp), -SPINE.down, SPINE_UP[SCEN.kind] ?? SPINE.up);
  hy = clamp(hy, -nY, nY); hp = clamp(hp, -NECK.down, nUp);
  const S = (C.hs ||= { y: hy, p: hp, sy, sp, vy: 0, vp: 0, vsy: 0, vsp: 0 }), w = 6, ws = 4;
  for (let n = 0, h = dt / 2; n < 2; n++) {
    S.vy += (w * w * (hy - S.y) - 2 * w * S.vy) * h; S.y += S.vy * h;
    S.vp += (w * w * (hp - S.p) - 2 * w * S.vp) * h; S.p += S.vp * h;
    S.vsy += (ws * ws * (sy - S.sy) - 2 * ws * S.vsy) * h; S.sy += S.vsy * h;   // the torso follows more slowly
    S.vsp += (ws * ws * (sp - S.sp) - 2 * ws * S.vsp) * h; S.sp += S.vsp * h;
  }
  C.gYaw = S.y; C.gPitch = S.p; C.sYaw = S.sy; C.sPitch = S.sp;
}
function gazeEyes(C, dt) {
  const ws = [], exs = [0, 0];
  for (const E of C.eyes) {
    const G = E.userData.G, U = E.material.userData.E; if (!G) continue;
    if (!GZ.on || !C.gTarget) { U.uEyeR.value.identity(); continue; }
    eyeA(E, G, _A); ws.push(G.c.clone().applyMatrix4(_A));
    _Ai.copy(_A).invert(); const d = C.gTarget.clone().applyMatrix4(_Ai).sub(G.c).normalize();
    let y = deg(Math.atan2(d.dot(G.r), d.dot(G.f))), p = deg(Math.asin(clamp(d.dot(G.u), -1, 1)));
    exs[0] += (y - clamp(y, -EYE.yaw, EYE.yaw)) / C.eyes.length; exs[1] += (p - clamp(p, -EYE.down, EYE.up)) / C.eyes.length;
    y = clamp(y + (C.gz ? C.gz.my : 0), -EYE.yaw, EYE.yaw); p = clamp(p + (C.gz ? C.gz.mp : 0), -EYE.down, EYE.up);
    const k = 1 - Math.exp(-dt / 0.035); G.yaw += (y - G.yaw) * k; G.pitch += (p - G.pitch) * k;   // saccade-fast
    const cy = Math.cos(rad(G.yaw)), sy = Math.sin(rad(G.yaw)), cp = Math.cos(rad(G.pitch)), sp = Math.sin(rad(G.pitch));
    _v1.copy(G.f).multiplyScalar(cp * cy).addScaledVector(G.r, cp * sy).addScaledVector(G.u, sp).normalize();
    _q.setFromUnitVectors(G.f, _v1); U.uEyeR.value.setFromMatrix4(_m4.makeRotationFromQuaternion(_q));
  }
  if (ws.length) C.eyesW = ws.reduce((a, b) => a.add(b), new THREE.Vector3()).multiplyScalar(1 / ws.length);
  C.eyeEx = exs;
}

// ---- emotion gain ----
const emo = $('emo');
emo.min = LEVELS[0]; emo.max = LEVELS[LEVELS.length - 1]; emo.step = 0.05;
$('emoTicks').innerHTML = LEVELS.map((v) => `<option value="${v}"></option>`).join('');
$('emoLevels').textContent = LEVELS.length > 1 ? 'Baked: ' + LEVELS.join(' · ') + ' (in between = blend)' : 'Only the approved 1.6 is baked in this build.';
function setEmo(v) { EMO = +v; LV = levelAt(EMO); emo.value = EMO; $('emoVal').textContent = EMO.toFixed(2) + '×'; store.set('emo', EMO); }
emo.oninput = (e) => setEmo(e.target.value);
$('emoReset').onclick = () => setEmo(1.6);
emo.disabled = LEVELS.length < 2; setEmo(LEVELS.length > 1 ? store.get('emo', 1.6) : 1.6);

// ---- light sliders ----
const LIGHT_UI = [['exposure', 'Exposure', 0.4, 2.5, 0.05], ['key', 'Key light', 0, 6, 0.1], ['keyAz', 'Key angle (°)', -150, 150, 1],
  ['keyEl', 'Key height (°)', -10, 85, 1], ['keyWarm', 'Key warmth', 0, 1, 0.05], ['fill', 'Fill', 0, 3, 0.05], ['rim', 'Rim / back', 0, 4, 0.05],
  ['ambient', 'Ambient', 0, 2, 0.05]];
Object.assign(LIGHT, store.get('light', {}));
$('lights').innerHTML = LIGHT_UI.map(([k, label, mn, mx, st]) =>
  `<div class="slider"><span>${label}</span><input type="range" id="lt_${k}" min="${mn}" max="${mx}" step="any"><output id="lv_${k}"></output></div>`).join('');
function syncLightUI() { for (const [k] of LIGHT_UI) { $('lt_' + k).value = LIGHT[k]; $('lv_' + k).textContent = (+LIGHT[k]).toFixed(k.startsWith('key') && k !== 'key' && k !== 'keyWarm' ? 0 : 2); } }
for (const [k] of LIGHT_UI) $('lt_' + k).oninput = (e) => { LIGHT[k] = +e.target.value; syncLightUI(); applyLight(); store.set('light', LIGHT); };
$('lightReset').onclick = () => { Object.assign(LIGHT, LIGHT_DEFAULT); syncLightUI(); applyLight(); store.set('light', LIGHT); };
syncLightUI(); applyLight();

// ---- Motion section: pose + [min, max] ranges -> preview takes sampled inside them, save several motions per pose ----
const PN = poseNames(POSES); Object.assign(PN, store.get('poseNames', {}));  // user renames win
const M_UI = [['blendIn', 'Blend in (s)', 0.05, 2.5, 0.05], ['inEaseIn', 'In: ease in', 0, 1, 0.05], ['inEaseOut', 'In: ease out', 0, 1, 0.05],
  ['hold', 'Hold (s)', -2, 3, 0.05], ['blendOut', 'Blend out (s)', 0.05, 3, 0.05], ['outEaseIn', 'Out: ease in', 0, 1, 0.05], ['outEaseOut', 'Out: ease out', 0, 1, 0.05],
  ['sway', 'Idle sway', 0, 1, 0.05], ['strength', 'Strength', 0, 1.2, 0.05]];
const R_DEFAULT = { blendIn: [0.35, 0.6], inEaseIn: [0.3, 0.5], inEaseOut: [0.5, 0.7], hold: [0.3, 0.9], blendOut: [0.55, 0.9],
  outEaseIn: [0.4, 0.6], outEaseOut: [0.4, 0.6], sway: [0.4, 0.6], strength: [0.85, 1] };
const fmt = (k, v) => k === 'sway' || k === 'strength' ? Math.round(v * 100) + '%' : (+v).toFixed(2);
const poseFrame = (i) => (meta.poseFrames ? meta.poseFrames[i] : i + 1);  // frame in the user's FBX
function fillPoses() { $('mPose').innerHTML = PN.map((n, i) => i ? `<option value="${i}">${n}  (frame ${poseFrame(i)})</option>` : '').join(''); $('mPose').value = MR.pose; }
$('mSliders').innerHTML = M_UI.map(([k, label, mn, mx, st]) =>
  `<div class="slider"><span>${label}</span><div class="dual" id="md_${k}"><div class="band"></div>` +
  `<input type="range" class="lo" id="mlo_${k}" min="${mn}" max="${mx}" step="any"><input type="range" class="hi" id="mhi_${k}" min="${mn}" max="${mx}" step="any"></div>` +
  `<output id="mv_${k}"></output></div>`).join('');
{ const saved = store.get('motionRanges', null);
  MR.pose = saved && saved.pose >= 1 && saved.pose < POSES.count ? saved.pose : 1; MR.loaded = saved ? saved.loaded || null : null;
  for (const [k] of M_UI) MR.r[k] = (saved && saved.r && saved.r[k]) ? [...saved.r[k]] : [...R_DEFAULT[k]]; }
fillPoses();
// sample one take: every parameter uniformly inside its [min, max]
// ONE variation value u (0..1) per take drives every parameter: u = 0.5 puts all of them half-way in their ranges, so a
// take stays coherent (user). mode 'random' draws u, 'min' / 'max' play the bounds (u = 0 / 1).
function takeAt(R, u) { const P = { pose: R.pose, u }; for (const [k] of M_UI) { const [lo, hi] = R.r[k]; P[k] = lo + u * (hi - lo); } return P; }
function sampleTake(R, mode = 'random') { return takeAt(R, mode === 'min' ? 0 : mode === 'max' ? 1 : Math.random()); }
function newTake() { INST = sampleTake(MR, prev.mode); showTake(); }
function showTake() { $('mTake').textContent = (prev.mode === 'min' ? 'Left bounds: in ' : prev.mode === 'max' ? 'Right bounds: in ' : 'This take (' + Math.round(INST.u * 100) + '%): in ') + INST.blendIn.toFixed(2) + ' s · hold ' + INST.hold.toFixed(2) + ' s · out ' + INST.blendOut.toFixed(2) + ' s · sway ' + Math.round(INST.sway * 100) + '% · strength ' + Math.round(INST.strength * 100) + '%'; }
function syncMotionUI() {
  $('mPose').value = MR.pose;
  for (const [k, , mn, mx] of M_UI) {
    const [lo, hi] = MR.r[k]; $('mlo_' + k).value = lo; $('mhi_' + k).value = hi;
    const pct = k === 'sway' || k === 'strength';
    $('mv_' + k).textContent = lo === hi ? fmt(k, lo) : (pct ? Math.round(lo * 100) : fmt(k, lo)) + '–' + fmt(k, hi);
    const band = $('md_' + k).firstChild; band.style.left = ((lo - mn) / (mx - mn) * 100) + '%'; band.style.width = ((hi - lo) / (mx - mn) * 100) + '%';
  }
  $('mPlay').classList.toggle('on', prev.on && prev.mode === 'random'); $('mPlayMin').classList.toggle('on', prev.on && prev.mode === 'min');
  $('mPlayMax').classList.toggle('on', prev.on && prev.mode === 'max'); renderList(); drawCurve(prev.on ? prev.tau - prev.lead : null);
}
const editChanged = () => { store.set('motionRanges', MR); INST = { ...INST, pose: MR.pose }; syncMotionUI(); };
// the saved profile currently loaded for this pose (Save overwrites it); remembered per pose
const lastByPose = store.get('motionLast', {});
const loadedMotion = () => MOTIONS.find((m) => m.id === MR.loaded && m.pose === MR.pose) || null;
const isDirty = () => { const m = loadedMotion(); return !m || JSON.stringify(m.ranges) !== JSON.stringify(MR.r); };
for (const [k] of M_UI) {
  $('mlo_' + k).oninput = (e) => { const v = +e.target.value; MR.r[k] = [v, Math.max(v, MR.r[k][1])]; editChanged(); };
  $('mhi_' + k).oninput = (e) => { const v = +e.target.value; MR.r[k] = [Math.min(v, MR.r[k][0]), v]; editChanged(); };
}
// changing pose keeps the current blend ranges, unless that pose has a saved profile: then it snaps to it
$('mPose').onchange = (e) => {
  MR.pose = +e.target.value;
  const mine = MOTIONS.filter((m) => m.pose === MR.pose);
  const m = mine.find((x) => x.id === lastByPose[MR.pose]) || mine[mine.length - 1];
  if (m) loadRanges(m); else { MR.loaded = null; editChanged(); }
};
$('mRename').onclick = () => {
  const name = ($('mName').value || '').trim(); if (!name) { $('mState').textContent = 'Type the new pose name in the name box first.'; return; }
  PN[MR.pose] = name; store.set('poseNames', Object.fromEntries(PN.map((v, i) => [i, v]))); $('mName').value = '';
  for (const m of MOTIONS) if (m.pose === MR.pose) m.poseName = name; saveMotions(); fillPoses(); renderList();
};
function startPreview(mode = 'random') { if (playing) pause(); prev.mode = mode; newTake(); prev.on = true; prev.tau = 0; syncMotionUI(); }
function stopPreview() { if (!prev.on) return; prev.on = false; syncMotionUI(); }
$('mPlay').onclick = () => startPreview('random'); $('mPlayMin').onclick = () => startPreview('min'); $('mPlayMax').onclick = () => startPreview('max');
$('mStop').onclick = stopPreview;
$('mLoop').checked = prev.loop; $('mLoop').onchange = (e) => { prev.loop = e.target.checked; };
// curves: faint = a spread of possible takes inside the ranges, bright = the take playing now (with playhead)
let spreadKey = '', spread = null;  // cached faint curves (recomputed only when the ranges change)
function drawCurve(at) {
  const cv = $('mCurve'); if (cv.clientWidth && cv.width !== cv.clientWidth) cv.width = cv.clientWidth;  // follows the panel width
  const g = cv.getContext('2d'), W = cv.width, H = cv.height;
  const key = JSON.stringify(MR) + (prev.on ? motionLength(INST).toFixed(3) : '') + W;
  if (key !== spreadKey) {
    const takes = [...Array(11).keys()].map((i) => takeAt(MR, i / 10));  // the family of takes: u = 0, 10%, ... 100%
    const maxLen = Math.max(...takes.map(motionLength), prev.on ? motionLength(INST) : 0), len = prev.lead + maxLen + prev.tail;
    const off = document.createElement('canvas'); off.width = W; off.height = H; const o = off.getContext('2d');
    o.strokeStyle = '#3a3d44'; o.beginPath(); o.moveTo(0, H - 4); o.lineTo(W, H - 4); o.moveTo(0, 4); o.lineTo(W, 4); o.stroke();
    const plot = (P, style, lw) => { o.strokeStyle = style; o.lineWidth = lw; o.beginPath();
      for (let x = 0; x <= W; x++) { const tt = (x / W) * len - prev.lead, y = H - 4 - weightAt(P, tt) * (H - 8); x ? o.lineTo(x, y) : o.moveTo(x, y); } o.stroke(); };
    for (const P of takes) plot(P, 'rgba(217,163,91,0.22)', 1);
    if (prev.on) plot(INST, '#d9a35b', 2);
    const ls = takes.map(motionLength); $('mLen').textContent = Math.min(...ls).toFixed(2) + '–' + Math.max(...ls).toFixed(2) + ' s';
    spread = { img: off, len }; spreadKey = key;
  }
  g.clearRect(0, 0, W, H); g.drawImage(spread.img, 0, 0);
  if (at !== null && at !== undefined) { const x = ((at + prev.lead) / spread.len) * W; g.strokeStyle = '#e8e6e1'; g.lineWidth = 1; g.beginPath(); g.moveTo(x, 0); g.lineTo(x, H); g.stroke(); }
}
// saved motions (motions.json next to the lab, via server.py): a pose + its parameter ranges
let MOTIONS = [];
try { const r = await fetch('motions', { cache: 'no-store' }); if (r.ok) MOTIONS = (await r.json()).motions || []; } catch (e) {}
function saveMotions() {
  const body = { version: 3, poseNames: PN, note: 'ranges[k] = [min, max]; each replay draws ONE u in [0,1] and sets every parameter to min + u*(max-min) ' +
    '(blend in/out in s with bezier ease in/out 0-1, hold in s and may be negative, sway and strength 0-1+)', motions: MOTIONS };
  fetch('motions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    .then((r) => { $('mState').textContent = r.ok ? 'Saved ' + MOTIONS.length + ' motions' : 'NOT saved'; }).catch(() => { $('mState').textContent = 'NOT saved (server)'; });
  replan();
}
// ---- gestures on the speech ----
const ARMS = poseArms(POSES);
function replan(opts) { SPEECH = SCRIPT ? planSpeech(SCRIPT, MOTIONS, PN, takeAt, ARMS, opts) : []; renderSpeech(); }
function renderSpeech() {
  if (!SCRIPT) { $('spList').innerHTML = '<div class="hint">No data/script.json: speech placement unavailable.</div>'; return; }
  $('spList').innerHTML = SPEECH.length ? SPEECH.map((e, i) => `<button class="sprow" data-sp="${i}" title="Jump there">${e.chain ? '&nbsp;&nbsp;↳ ' : ''}${e.apex.toFixed(2)} s · ${e.char === 'S1' ? 'Seller' : 'Customer'} · ${PN[e.pose]} (${ARMS[e.pose] === 'both' ? 'both arms' : ARMS[e.pose] === 'L' ? 'left arm' : 'right arm'}) · ${Math.round(e.u * 100)}% · ${e.mood === '_' ? 'neutral' : e.mood.toLowerCase()}</button>`).join('')
    : '<div class="hint">Save pose profiles to place gestures on the dialogue.</div>';
  $('spList').querySelectorAll('[data-sp]').forEach((b) => b.onclick = () => { stopPreview(); t = Math.max(0, SPEECH[+b.dataset.sp].start - 0.4); });
}
SP.on = store.get('speechGestures', true); $('spOn').checked = SP.on;
$('spOn').onchange = (e) => { SP.on = e.target.checked; store.set('speechGestures', SP.on); };
function loadRanges(m) {
  MR.pose = m.pose; MR.loaded = m.id; lastByPose[m.pose] = m.id; store.set('motionLast', lastByPose);
  for (const [k] of M_UI) MR.r[k] = m.ranges && m.ranges[k] ? [...m.ranges[k]] : [...R_DEFAULT[k]]; editChanged();
}
function renderList() {
  const mine = MOTIONS.filter((m) => m.pose === MR.pose);
  const lm = loadedMotion(), dirty = isDirty();
  $('mSave').textContent = lm ? (dirty ? 'Save •' : 'Saved') : 'Save'; $('mSave').classList.toggle('on', !!lm && dirty);
  $('mSave').title = lm ? 'Overwrite "' + lm.name + '" with the current ranges' : 'Save the current ranges as a new profile for this pose';
  $('mList').innerHTML = mine.length ? mine.map((m) => `<div class="mrow"><button data-load="${m.id}" title="Load"${m.id === MR.loaded ? ' class="on"' : ''}>${m.name}</button><button data-play="${m.id}" title="Load and preview">▶</button><button data-del="${m.id}" title="Delete">✕</button></div>`).join('')
    : `<div class="hint">No saved motions for ${PN[MR.pose]} yet.</div>`;
  const byId = (id) => MOTIONS.find((m) => m.id === id);
  $('mList').querySelectorAll('[data-load]').forEach((b) => b.onclick = () => loadRanges(byId(b.dataset.load)));
  $('mList').querySelectorAll('[data-play]').forEach((b) => b.onclick = () => { loadRanges(byId(b.dataset.play)); startPreview(); });
  $('mList').querySelectorAll('[data-del]').forEach((b) => b.onclick = () => { MOTIONS = MOTIONS.filter((m) => m.id !== b.dataset.del); if (MR.loaded === b.dataset.del) MR.loaded = null; saveMotions(); renderList(); });
}
function saveNew() {
  const n = MOTIONS.filter((m) => m.pose === MR.pose).length + 1;
  const name = ($('mName').value || '').trim() || `${PN[MR.pose]} #${n}`;
  const m = { id: Date.now().toString(36), name, pose: MR.pose, poseName: PN[MR.pose], ranges: JSON.parse(JSON.stringify(MR.r)), created: new Date().toISOString() };
  MOTIONS.push(m); $('mName').value = ''; saveMotions(); loadRanges(m);
}
// Save = overwrite the loaded profile of this pose (or create the first one); Save as new = another profile
$('mSave').onclick = () => {
  const m = loadedMotion(); if (!m) return saveNew();
  m.ranges = JSON.parse(JSON.stringify(MR.r)); m.updated = new Date().toISOString();
  const nm = ($('mName').value || '').trim(); if (nm) { m.name = nm; $('mName').value = ''; }
  saveMotions(); renderList();
};
$('mSaveNew').onclick = saveNew;
if (POSES.count < 2) { $('mState').textContent = 'No Poses clip in boss.glb: rebuild with --poses.'; }
INST = sampleTake(MR); syncMotionUI(); replan();

$('snap').onclick = async () => {
  const image = renderer.domElement.toDataURL('image/png');
  const state = { t, frame: Math.round(t * FPS), playing, speed, layers: L, emotionGain: EMO, light: LIGHT, motion: { pose: MR.pose, ranges: MR.r, take: INST, previewing: prev.on, previewTime: prev.tau - prev.lead }, line: $('line').textContent,
    camera: { pos: camera.position.toArray(), target: controls.target.toArray() }, time: new Date().toISOString() };
  const r = await fetch('snapshot', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image, ...state }) });
  $('snapState').textContent = r.ok ? 'Saved at ' + t.toFixed(2) + ' s' : 'Snapshot failed';
};
window.lab = { NECKFIX, SCEN, GZ, setScenario, layout, frame: (dt) => frame(dt), get t() { return t; }, set t(v) { t = v; }, chars, L, setEmo, MR, get INST() { return INST; }, get SPEECH() { return SPEECH; }, SP, replan, prev, POSES, startPreview, stopPreview, syncMotionUI, LIGHT, applyLight, setCam, meta, cam: camera, ctl: controls, renderer, V3: THREE.Vector3, THREE };

function lineAt(time) { return meta.lines.find((l) => time >= l.start && time < l.start + l.dur); }
function tick() { frame(); requestAnimationFrame(tick); }

function frame(dtForced) {   // one frame (window.lab.frame lets Claude step the lab while the pane is hidden)
  const dt = dtForced ?? Math.min(clock.getDelta(), 0.1);
  if (ARROW.dir && performance.now() - ARROW.since > 120) t = Math.min(T, Math.max(0, t + ARROW.dir * dt));   // held arrow: scrub at 1x
  if (playing) {
    t = clockRef === null ? tRef + (actx.currentTime - audioRef) : tRef + (performance.now() / 1000 - clockRef) * speed;
    if (t >= T) { t = T; pause(); }
  }
  for (const id of activeIds()) {
    const C = chars[id];
    // undo last frame's additive head rotation: the mixer only rewrites a bone when its value changes (e.g. paused)
    for (const [b, q] of C.pre) b.quaternion.copy(q);
    posers[id].restore();  // and last frame's pose blend
    for (const [b, q, p] of C.damp) { b.quaternion.copy(q); b.position.copy(p); }  // and last frame's idle-sway damping
    C.damp.length = 0;
    for (const a of Object.values(C.acts)) a.setEffectiveWeight(L.body && a === C.act ? 1 : 0);  // all 0 -> bind pose (Boss A-pose)
    C.mixer.update(L.body ? (playing ? dt * speed : prev.on ? dt : 0) : 0);  // the idle keeps breathing during a preview
    if (L.body) dampIdle(C, swayFor(id, t));
  }
  poseAt(t);
  scene.updateMatrixWorld(true);
  if (prev.on) {
    prev.tau += dt; const len = prev.lead + motionLength(INST) + prev.tail;
    if (prev.tau > len) { if (prev.loop) { prev.tau -= len; newTake(); } else stopPreview(); }
    const w = weightAt(INST, prev.tau - prev.lead);
    if (prev.on) { for (const id of activeIds()) posers[id].apply(INST.pose, w, INST.sway, INST.strength, SCEN.kind !== 'stand' && SCEN.kind !== 'group'); scene.updateMatrixWorld(true); }  // profiles are for every character: preview on both
    drawCurve(prev.tau - prev.lead);
  } else if (SP.on && L.body) {  // gestures placed on the dialogue (deterministic, follow the timeline / scrubbing)
    let any = false;
    for (const ev of SPEECH) { const tt = t - ev.start; if (tt > 0 && tt < motionLength(ev.P)) { posers[ev.char].apply(ev.pose, weightAt(ev.P, tt), ev.P.sway, ev.P.strength * chars[ev.char].amp, SCEN.kind !== 'stand' && SCEN.kind !== 'group'); any = true; } }
    if (any) scene.updateMatrixWorld(true);
  }
  if (stoolPending && !--stoolPending) placeStool();
  const act = activeIds();
  for (const id of act) gazeHead(id, dt);
  for (const id of act) applyHead(chars[id]);
  for (const id of act) gazeEyes(chars[id], dt);
  if (camPending && !--camPending) setCam(CURCAM);
  const l = lineAt(t);
  $('line').textContent = l ? (l.speaker === 'S1' ? 'Seller: ' : 'Customer: ') + l.english : '';
  $('time').textContent = t.toFixed(2) + ' s'; $('frame').textContent = 'f ' + Math.round(t * FPS);
  if (!$('scrub').matches(':active')) $('scrub').value = Math.round((t / T) * 1000);
  controls.update(); renderer.render(scene, camera);
}
setScenario(SCEN.kind);
setCam('two');
$('loading').remove();
tick();
