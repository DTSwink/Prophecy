// Speech-pose motions: blend the game idle into one of the user's authored poses and back.
// Poses come from the 'Poses' clip in boss.glb (frame 0 = the idle reference the poses were authored on).
// A motion = pose + blend-in (duration, ease in/out) + hold (may be negative: blend-out starts before the pose is
// reached) + blend-out (duration, ease in/out) + how much of the idle's sway stays alive in the pose + strength.
import * as THREE from 'three';

// default names read from the pose data: the shrug lifts BOTH clavicles, the plead bends BOTH forearms; the rest are
// numbered in file order (names can be changed in the lab, they are saved in settings)
export function poseNames(P) {
  const n = P.count; if (n < 2) return ['Idle (reference)'];
  const ang = (b, k) => (P.bones[b] && P.bones[b].q ? P.bones[b].q[k].angleTo(P.bones[b].q[0]) * 180 / Math.PI : 0);
  let shrug = -1, plead = -1, bs = 6, bp = 45;
  for (let k = 1; k < n; k++) {
    const c = Math.min(ang('clavicle_l', k), ang('clavicle_r', k)); if (c > bs) { bs = c; shrug = k; }
    const f = Math.min(ang('lowerarm_l', k), ang('lowerarm_r', k)); if (f > bp) { bp = f; plead = k; }
  }
  let i = 0; return [...Array(n).keys()].map((k) => k === 0 ? 'Idle (reference)' : k === shrug ? 'Shrug' : k === plead ? 'Plead' : 'Pose ' + (++i));
}
export const DEFAULT_PARAMS = { pose: 1, blendIn: 0.45, inEaseIn: 0.4, inEaseOut: 0.6, hold: 0.6, blendOut: 0.7, outEaseIn: 0.5, outEaseOut: 0.5, sway: 0.5, strength: 1 };

// ---- poses from the glTF clip ----
const FINGER = /^(thumb|index|middle|ring|pinky)_/;
export function loadPoses(clip) {
  const out = { count: 0, bones: {} };  // bones[name] = { q: [Quaternion per pose], p: [Vector3 per pose] | null }
  if (!clip) return out;
  const n = Math.round(clip.duration * 30) + 1; out.count = n;
  for (const tr of clip.tracks) {
    const [bone, prop] = tr.name.split('.'); if (bone.startsWith('ik_') || (prop !== 'quaternion' && prop !== 'position')) continue;
    if (FINGER.test(bone)) continue;  // user: fingers stay as the normal idle has them
    const ip = tr.createInterpolant(); const e = (out.bones[bone] ||= { q: null, p: null });
    if (prop === 'quaternion') e.q = [...Array(n).keys()].map((i) => new THREE.Quaternion().fromArray(ip.evaluate(i / 30)).normalize());
    else e.p = [...Array(n).keys()].map((i) => new THREE.Vector3().fromArray(ip.evaluate(i / 30)));
  }
  // drop bones the poses never move (keeps the per-frame work small)
  for (const [b, e] of Object.entries(out.bones)) {
    const moved = (e.q && e.q.some((q) => q.angleTo(e.q[0]) > 1e-4)) || (e.p && e.p.some((p) => p.distanceTo(e.p[0]) > 1e-5));
    if (!moved) delete out.bones[b];
  }
  return out;
}

// ---- easing: cubic bezier (0,0) (easeIn,0) (1-easeOut,1) (1,1); 0/0 = linear, 1/1 = very soft both ends ----
export function ease(x, ei, eo) {
  x = Math.min(Math.max(x, 0), 1); if (x === 0 || x === 1) return x;
  const x1 = ei, x2 = 1 - eo;
  const bx = (u) => 3 * (1 - u) * (1 - u) * u * x1 + 3 * (1 - u) * u * u * x2 + u * u * u;
  const by = (u) => 3 * (1 - u) * u * u + u * u * u;
  let lo = 0, hi = 1, u = x; for (let i = 0; i < 30; i++) { u = (lo + hi) / 2; if (bx(u) < x) lo = u; else hi = u; }
  return by(u);
}
// pose weight at time t (s) from the start of the blend-in
export function weightAt(P, t) {
  const hold = Math.max(P.hold, -P.blendIn);  // can't start leaving before starting to arrive
  const wi = ease(t / Math.max(P.blendIn, 1e-3), P.inEaseIn, P.inEaseOut);
  const wo = 1 - ease((t - P.blendIn - hold) / Math.max(P.blendOut, 1e-3), P.outEaseIn, P.outEaseOut);
  return Math.max(0, Math.min(1, wi * wo));
}
export const motionLength = (P) => P.blendIn + Math.max(P.hold, -P.blendIn) + P.blendOut;

// ---- applying a pose on a character, on top of whatever the idle mixer produced this frame ----
export function createPoser(C, poses) {
  const saved = new Map();
  const _a = new THREE.Quaternion(), _t = new THREE.Quaternion(), _v = new THREE.Vector3();
  function restore() { for (const [b, [q, p]] of saved) { b.quaternion.copy(q); b.position.copy(p); } saved.clear(); }
  function apply(k, w, sway, strength) {
    if (!(w > 0) || k <= 0 || k >= poses.count) return;
    const a = w * strength;
    for (const [name, e] of Object.entries(poses.bones)) {
      const b = C.bones[name]; if (!b) continue;
      if (!saved.has(b)) saved.set(b, [b.quaternion.clone(), b.position.clone()]);
      const [idleQ, idleP] = saved.get(b);  // the live idle of this frame (before any pose), even when poses chain
      if (e.q) {
        // additive version: the pose's offset from the idle reference, laid on the live idle (keeps its sway)
        _a.copy(e.q[k]).multiply(_t.copy(e.q[0]).invert()).multiply(idleQ);
        const target = _t.copy(e.q[k]).slerp(_a, sway);
        b.quaternion.slerp(target, a);  // from whatever is there (idle, or the previous pose of a chain)
      }
      if (e.p) {
        const add = _v.copy(e.p[k]).sub(e.p[0]).add(idleP);
        const target = e.p[k].clone().lerp(add, sway);
        b.position.lerp(target, a);
      }
    }
  }
  return { apply, restore };
}

// which arm a pose uses: 'L', 'R' or 'both' (rotation of upper arm + forearm + hand vs the idle reference)
export function poseArms(P) {
  const ang = (b, k) => (P.bones[b] && P.bones[b].q ? P.bones[b].q[k].angleTo(P.bones[b].q[0]) : 0);
  return [...Array(P.count).keys()].map((k) => {
    if (!k) return null;
    const l = ang('upperarm_l', k) + ang('lowerarm_l', k) + ang('hand_l', k), r = ang('upperarm_r', k) + ang('lowerarm_r', k) + ang('hand_r', k);
    return l > 2 * r ? 'L' : r > 2 * l ? 'R' : 'both';
  });
}
