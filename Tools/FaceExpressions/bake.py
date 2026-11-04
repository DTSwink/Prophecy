"""Bake expression deltas on Ada (LOD0-quality head sampled onto LOD3, other parts at LOD3) and map them to the boss."""
import numpy as np, sys, json
from scipy.spatial import cKDTree
sys.path.insert(0, '/home/claude/face')
from rl import evaluate

E = 'CTRL_expressions.'
LR = lambda k, v: {k + 'L': v, k + 'R': v}

def mk(*parts, **single):
    d = {}
    for p in parts: d.update(p)
    d.update(single); return d

EXPRESSIONS = {
    'Blink_L': {'eyeBlinkL': 1},
    'Blink_R': {'eyeBlinkR': 1},
    'JawOpen': {'jawOpen': 1},
    'Effort': mk(LR('browDown', .7), LR('eyeSquintInner', .6), LR('eyeCheekRaise', .5), LR('noseWrinkle', .5),
                 LR('mouthStretch', .6), LR('mouthUpperLipRaise', .45), LR('mouthLowerLipDepress', .45), LR('jawClench', 1)),
    'Pain': mk(LR('browRaiseIn', .8), LR('browDown', .5), LR('eyeSquintInner', .8), LR('eyeBlink', .45), LR('eyeCheekRaise', .7),
               LR('noseWrinkle', .7), LR('mouthStretch', .8), LR('mouthUpperLipRaise', .6), LR('mouthCornerDepress', .4), jawOpen=.25),
    'Shout': mk(LR('browDown', .9), LR('browLateral', .5), LR('eyeSquintInner', .3), LR('noseWrinkle', .5), LR('mouthUpperLipRaise', .6),
                LR('mouthStretch', .4), LR('neckStretch', .5), jawOpen=.75),
    'Anger': mk(LR('browDown', 1), LR('browLateral', .6), LR('eyeSquintInner', .4), LR('eyeUpperLidUp', .25), LR('noseWrinkle', .3),
                LR('mouthPressU', .5), LR('mouthPressD', .5), LR('mouthCornerDepress', .3), LR('jawClench', .5)),
    'Fear': mk(LR('browRaiseIn', 1), LR('browRaiseOuter', .7), LR('eyeWiden', 1), LR('mouthStretch', .5), jawOpen=.3),
    'Grin': mk(LR('mouthCornerPull', 1), LR('eyeCheekRaise', .6), LR('mouthUpperLipRaise', .3), LR('mouthStretch', .2)),
    'Dead': mk(LR('eyeBlink', .6), LR('eyeRelax', 1), LR('mouthLowerLipDepress', .2), jawOpen=.35),
    'LookLeft': mk(LR('eyeLookLeft', .7)),
    'LookRight': mk(LR('eyeLookRight', .7)),
    'LookUp': mk(LR('eyeLookUp', .7)),
    'LookDown': mk(LR('eyeLookDown', .7)),
}

def raw_vec(d, ctrl):
    names = list(d['raw_names']); x = np.zeros(len(names))
    for k, v in ctrl.items(): x[names.index(E + k)] = v
    return x

def lod0_to_lod3_sampler(d0, d3):
    """barycentric weights of every LOD3 head vertex on the LOD0 neutral surface"""
    V0 = d0['V']; tris = []
    fl = d0['face_len']; fi = d0['lay_pos'][d0['face_idx']]; o = 0
    for n in fl:
        f = fi[o:o + n]; o += n
        for k in range(1, n - 1): tris.append((f[0], f[k], f[k + 1]))
    tris = np.array(tris)
    cent = V0[tris].mean(1); tree = cKDTree(cent)
    P = d3['V']; _, cand = tree.query(P, k=16)
    best_tri = np.zeros(len(P), int); best_w = np.zeros((len(P), 3)); best_d = np.full(len(P), np.inf)
    for c in range(cand.shape[1]):
        T = V0[tris[cand[:, c]]]
        a, b, cc = T[:, 0], T[:, 1], T[:, 2]
        v0, v1, v2 = b - a, cc - a, P - a
        d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1); d20 = (v2 * v0).sum(1); d21 = (v2 * v1).sum(1)
        den = d00 * d11 - d01 * d01 + 1e-12
        v = (d11 * d20 - d01 * d21) / den; w = (d00 * d21 - d01 * d20) / den
        bc = np.clip(np.stack([1 - v - w, v, w], 1), 0, 1); bc /= bc.sum(1, keepdims=True)
        proj = (T * bc[:, :, None]).sum(1); dist = np.linalg.norm(proj - P, axis=1)
        m = dist < best_d
        best_d[m] = dist[m]; best_tri[m] = cand[m, c]; best_w[m] = bc[m]
    return tris[best_tri], best_w, best_d

if __name__ == '__main__':
    F = '/home/claude/face/'
    d0 = dict(np.load(F + 'ada_head_lod0.npz'))
    parts = {7: 26, 1: 27, 2: 28, 3: 29, 4: 30, 6: 31, 5: 32}
    D = {m: dict(np.load(F + f'ada_m{am}.npz')) for m, am in parts.items()}
    tri, bw, bd = lod0_to_lod3_sampler(d0, D[7])
    print('LOD3->LOD0 surface dist cm mean/max', bd.mean().round(4), bd.max().round(4))
    al = np.load(F + 'align.npz'); sc, R = float(al['sc']), al['R']
    corr = dict(np.load(F + 'corr.npz'))
    neutral0 = evaluate(d0, raw_vec(d0, {}))
    neutral = {m: evaluate(D[m], raw_vec(D[m], {})) for m in parts}
    out = {}; stats = {}
    for name, ctrl in EXPRESSIONS.items():
        full = {}
        # head: LOD0-quality deltas sampled at LOD3 vertices
        p0 = evaluate(d0, raw_vec(d0, ctrl)) - neutral0
        head_hi = (p0[tri] * bw[:, :, None]).sum(1)
        head_lo = evaluate(D[7], raw_vec(D[7], ctrl)) - neutral[7]
        for m in parts:
            delta = head_hi if m == 7 else evaluate(D[m], raw_vec(D[m], ctrl)) - neutral[m]
            bverts, averts = corr[f'b{m}'], corr[f'a{m}']
            full[m] = (bverts, (sc * (R @ delta[averts].T)).T)  # cm->m, Y-up -> boss world
        idx = np.concatenate([v[0] for v in full.values()]); dl = np.concatenate([v[1] for v in full.values()])
        out[name + '_idx'] = idx; out[name + '_d'] = dl
        stats[name] = dict(max_mm=float(np.linalg.norm(dl, axis=1).max() * 1000),
                           hi_vs_lo_head_mm=float(np.linalg.norm(head_hi - head_lo, axis=1).max() * 10))
        print(name, {k: round(v, 2) for k, v in stats[name].items()})
    np.savez_compressed(F + 'boss_deltas.npz', names=np.array(list(EXPRESSIONS)), **out)
    json.dump(dict(expressions=EXPRESSIONS, stats=stats), open(F + 'bake_report.json', 'w'), indent=1)
