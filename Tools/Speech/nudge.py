"""Gentle melody nudge (v2 of prosody transfer, after the robotic first attempt).

The gibberish take keeps its OWN pitch contour (all natural wobble, consonant effects, voice character) and its own
timing (no stretching). We only add a slow correction curve delta(t) (semitones) built from two things the English
take tells us:
  1. word level: how high each word sits relative to the speaker's median (peaks/emphasis land on the right words)
  2. sentence endings: rise vs fall over the last word (question vs statement)
delta: word heights from the English (cap 3 st), the English peak word made the top of its sentence, the
sentence ending ramped toward the English rise/fall (cap 5 st); smoothed ~120 ms, scaled by `strength`;
new F0 = own F0 * 2^(delta/12) at every original pitch point, resynthesised with Praat PSOLA.
"""
import numpy as np
import parselmouth
from parselmouth.praat import call
import analyze as A

def voiced_span(t, s, a, b):
    m = (t >= a) & (t <= b) & ~np.isnan(s)
    return (t[m][0], t[m][-1]) if m.sum() >= 4 else None

def slope(t, s, a, b):
    m = (t >= a) & (t <= b) & ~np.isnan(s)
    if m.sum() < 4: return np.nan
    tt, yy = t[m][-30:], s[m][-30:]
    return np.polyfit(tt, yy, 1)[0] * (tt[-1] - tt[0])

def build_delta(tg, sg, gw, gmap, te, se, ew, scale=1.0, strength=1.0, cap=3.0, peak=True, end_cap=5.0, end_weight=1.0):
    """slow correction curve (semitones) on a 5 ms grid"""
    gp, ep = A.word_pitch(tg, sg, gw), A.word_pitch(te, se, ew)
    g_med, e_med = np.nanmedian(sg), np.nanmedian(se)
    wd = {}
    for i, m in enumerate(gmap):                                   # 1. word height
        src = m.get('src')
        if src is None or src >= len(ep) or np.isnan(gp[i][0]) or np.isnan(ep[src][0]): continue
        wd[i] = np.clip(g_med + scale * (ep[src][0] - e_med) - gp[i][0], -cap, cap)
    ramps = []
    for sent in A.sentences(gw):
        idx = [i for i in sent if gmap[i].get('src') is not None and gmap[i]['src'] < len(ep)]
        if not idx: continue
        if peak:                                                   # 2. the English peak word is the top of the sentence
            srcs = sorted({gmap[i]['src'] for i in idx})
            e_pk = max(srcs, key=lambda j: -1e9 if np.isnan(ep[j][1]) else ep[j][1])
            tops = {i: (gp[i][1] if not np.isnan(gp[i][1]) else -1e9) + wd.get(i, 0) for i in idx}
            g_pk = [i for i in idx if gmap[i]['src'] == e_pk and not np.isnan(gp[i][1])]
            if g_pk:
                i = max(g_pk, key=lambda k: tops[k]); others = max([v for k, v in tops.items() if k != i] or [-1e9])
                if tops[i] < others + 1.0: wd[i] = float(np.clip(wd.get(i, 0) + (others + 1.0 - tops[i]), -cap, cap))
        last = sent[-1]                                            # 3. sentence ending: rise vs fall like the English
        e_last = max(gmap[i]['src'] for i in idx)
        sp = voiced_span(tg, sg, gw[last][1], gw[last][2])
        se_, sg_ = slope(te, se, ew[e_last][1], ew[e_last][2]), slope(tg, sg, gw[last][1], gw[last][2])
        if sp and not (np.isnan(se_) or np.isnan(sg_)):
            ramps.append((sp[0], sp[1], float(np.clip(end_weight * scale * (se_ - sg_), -end_cap, end_cap))))
    T = np.arange(0, tg[-1] + 0.5, 0.005)
    if wd:
        pt = np.array([(gw[i][1] + gw[i][2]) / 2 for i in sorted(wd)]); pd = np.array([wd[i] for i in sorted(wd)])
        d = np.interp(T, pt, pd)
    else: d = np.zeros_like(T)
    k = int(0.12 / 0.005) | 1; w = np.hanning(k); w /= w.sum()
    d = np.convolve(np.pad(d, k // 2, mode='edge'), w, mode='valid')
    for a, b, ch in ramps:                                         # ramp anchored at the start of the voiced ending
        m = (T >= a) & (T <= b); d[m] += ch * (T[m] - a) / max(b - a, 1e-3)
        m2 = T > b; d[m2] += ch * np.exp(-(T[m2] - b) / 0.06)
    return T, np.clip(strength * d, -end_cap, end_cap)

def nudge(g_path, g_al, gmap, e_path, e_al, male, out_wav, **kw):
    gs, es = A.load(g_path), A.load(e_path)
    floor, ceil = (60, 320) if male else (110, 520)
    tg, sg = A.pitch(gs, male); te, se = A.pitch(es, male)
    gw, ew = A.words(g_al), A.words(e_al)
    T, d = build_delta(tg, sg, gw, gmap, te, se, ew, **kw)
    man = call(gs, 'To Manipulation', 0.01, floor, ceil)
    pt = call(man, 'Extract pitch tier')
    n = call(pt, 'Get number of points')
    new = call('Create PitchTier', 'p', 0, gs.duration)
    for i in range(1, n + 1):
        t = call(pt, 'Get time from index', i); f = call(pt, 'Get value at index', i)
        call(new, 'Add point', t, f * 2 ** (np.interp(t, T, d) / 12))
    call([man, new], 'Replace pitch tier')
    out = call(man, 'Get resynthesis (overlap-add)')
    out.save(out_wav, 'WAV')
    return out, (T, d)

def identity(g_path, male, out_wav):
    """PSOLA resynthesis with nothing changed (to measure what the resynthesis alone costs)"""
    gs = A.load(g_path); floor, ceil = (60, 320) if male else (110, 520)
    man = call(gs, 'To Manipulation', 0.01, floor, ceil)
    out = call(man, 'Get resynthesis (overlap-add)'); out.save(out_wav, 'WAV'); return out
