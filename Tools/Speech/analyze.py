"""Objective audio checks for the speech pipeline (cloud). Lets Claude filter takes before asking the user.

Per line (gibberish take + English reference + word map):
  melody  word_corr   correlation of per-word pitch (gibberish word vs the English word it carries), z-scored per line
          peak_match  fraction of sentences whose highest-pitched word is the one the English speaker peaked on
          end_match   fraction of sentences whose ending goes the same way (rise / fall) as the English
          range_st    pitch range (5th-95th percentile, semitones)
  damage  micro_st    natural pitch wobble (residual around a 100 ms smoothing); robotic takes lose it
          straight    fraction of voiced time where pitch moves in perfectly straight lines (synthetic glides)
          jumps       pitch jumps > 4 semitones between neighbouring frames inside voiced speech (glitches)
          hnr_db      harmonics-to-noise ratio (buzz/rasp changes it)
          dnsmos_sig / dnsmos_ovr  Microsoft DNSMOS P.835 speech quality (1..5), catches processing artefacts
"""
import json, re, subprocess, os, tempfile
import numpy as np
import parselmouth
from parselmouth.praat import call

DNSMOS_ONNX = '/tmp/claude-0/-home-claude/0fe64c57-808d-5039-ab94-85f914c99794/scratchpad/dl/sig_bak_ovr.onnx'
_sess = None

def load(path, sr=44100):
    with tempfile.TemporaryDirectory() as d:
        w = os.path.join(d, 'a.wav')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', path, '-ac', '1', '-ar', str(sr), w], check=True)
        return parselmouth.Sound(w)

def pitch(snd, male):
    floor, ceil = (60, 320) if male else (110, 520)
    p = snd.to_pitch_ac(time_step=0.01, pitch_floor=floor, pitch_ceiling=ceil)
    f = p.selected_array['frequency']; t = p.xs()
    st = np.full(len(f), np.nan); v = f > 0; st[v] = 12 * np.log2(f[v] / 100.0)
    return t, st

def words(al):
    cs, st, en = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
    out, cur = [], None
    for c, s, e in zip(cs, st, en):
        if c.isspace():
            if cur: out.append(cur); cur = None
            continue
        if cur is None: cur = [c, s, e]
        else: cur[0] += c; cur[2] = e
    if cur: out.append(cur)
    res, inside = [], False       # drop audio tags, including multi-word ones like [French accent]
    for w in out:
        if w[0].startswith('['): inside = True
        if not inside: res.append(w)
        if w[0].endswith(']'): inside = False
    return res

def word_pitch(t, st, ws):
    """mean and max pitch per word (nan if unvoiced)"""
    res = []
    for w, s, e in ws:
        m = (t >= s) & (t <= e) & ~np.isnan(st)
        res.append((np.nanmean(st[m]) if m.sum() >= 3 else np.nan, np.nanmax(st[m]) if m.sum() >= 3 else np.nan))
    return res

def runs(st):
    v = ~np.isnan(st); out = []; i = 0
    while i < len(st):
        if v[i]:
            j = i
            while j < len(st) and v[j]: j += 1
            out.append((i, j)); i = j
        else: i += 1
    return out

def damage(snd, male):
    t, st = pitch(snd, male)
    micro, straight_n, tot, jumps = [], 0, 0, 0
    for a, b in runs(st):
        seg = st[a:b]
        if len(seg) < 12: continue
        k = 11; sm = np.convolve(np.pad(seg, k // 2, mode='edge'), np.ones(k) / k, mode='valid')
        micro.append(np.std(seg - sm))
        d2 = np.abs(np.diff(seg, 2))
        straight_n += int(np.sum(np.convolve(d2 < 0.02, np.ones(5), mode='valid') >= 5)); tot += len(d2)
        jumps += int(np.sum(np.abs(np.diff(seg)) > 4))
    hnr = call(snd.to_harmonicity_cc(0.01, (60 if male else 110), 0.1, 1.0), 'Get mean', 0, 0)
    return dict(micro_st=float(np.mean(micro)) if micro else np.nan, straight=straight_n / max(tot, 1), jumps=jumps, hnr_db=float(hnr))

def dnsmos(snd):
    global _sess
    import onnxruntime as ort
    if _sess is None: _sess = ort.InferenceSession(DNSMOS_ONNX, providers=['CPUExecutionProvider'])
    y = call(snd, 'Resample', 16000, 50).values[0].astype('float32')
    L = int(9.01 * 16000)
    while len(y) < L: y = np.concatenate([y, y])
    sigs, ovrs = [], []
    for s in range(0, max(1, len(y) - L + 1), 16000):
        seg = y[s:s + L]
        if len(seg) < L: break
        sig, bak, ovr = _sess.run(None, {'input_1': seg[np.newaxis, :]})[0][0]
        sigs.append(np.poly1d([-0.08397278, 1.22083953, 0.0052439])(sig)); ovrs.append(np.poly1d([-0.06766283, 1.11546468, 0.04602535])(ovr))
    return float(np.mean(sigs)), float(np.mean(ovrs))

def sentences(ws):
    """indices of words grouped into sentences (split after . ! ?)"""
    out, cur = [], []
    for i, (w, s, e) in enumerate(ws):
        cur.append(i)
        if re.search(r'[.!?]["»]?$', w): out.append(cur); cur = []
    if cur: out.append(cur)
    return out

def ending(t, st, s, e):
    """direction of the pitch over the last ~350 ms of voiced speech in [s, e]: +1 rise, -1 fall, 0 flat"""
    m = (t >= s) & (t <= e) & ~np.isnan(st)
    if m.sum() < 6: return 0
    tt, yy = t[m][-35:], st[m][-35:]
    slope = np.polyfit(tt, yy, 1)[0] * (tt[-1] - tt[0])
    return 1 if slope > 1.0 else (-1 if slope < -1.0 else 0)

def melody(g_snd, g_al, gmap, e_snd, e_al, male_g, male_e=None):
    male_e = male_g if male_e is None else male_e
    tg, sg = pitch(g_snd, male_g); te, se = pitch(e_snd, male_e)
    gw, ew = words(g_al), words(e_al)
    assert len(gw) == len(gmap), (len(gw), len(gmap))
    gp, ep = word_pitch(tg, sg, gw), word_pitch(te, se, ew)
    pairs = [(gp[i][0], ep[m['src']][0]) for i, m in enumerate(gmap) if m.get('src') is not None and m['src'] < len(ep)]
    pairs = [(a, b) for a, b in pairs if not (np.isnan(a) or np.isnan(b))]
    if len(pairs) >= 3:
        a, b = np.array(pairs).T; a = (a - a.mean()) / (a.std() + 1e-6); b = (b - b.mean()) / (b.std() + 1e-6)
        corr = float(np.corrcoef(a, b)[0, 1])
    else: corr = np.nan
    peak_hits, end_hits, n = 0, 0, 0
    for sent in sentences(gw):
        srcs = [gmap[i]['src'] for i in sent if gmap[i].get('src') is not None]
        if not srcs: continue
        n += 1
        g_peak = max(sent, key=lambda i: (-1e9 if np.isnan(gp[i][1]) else gp[i][1]))
        e_cands = sorted(set(srcs))
        e_peak = max(e_cands, key=lambda j: (-1e9 if np.isnan(ep[j][1]) else ep[j][1]))
        peak_hits += int(gmap[g_peak].get('src') == e_peak)
        e_end = ending(te, se, ew[min(e_cands)][1], ew[max(e_cands)][2])
        g_end = ending(tg, sg, gw[sent[0]][1], gw[sent[-1]][2])
        end_hits += int(e_end == g_end)
    rng = float(np.nanpercentile(sg, 95) - np.nanpercentile(sg, 5))
    return dict(word_corr=corr, peak_match=peak_hits / max(n, 1), end_match=end_hits / max(n, 1), range_st=rng)

def plot(path_png, g_snd, g_al, gmap, e_snd, e_al, male, title=''):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    tg, sg = pitch(g_snd, male); te, se = pitch(e_snd, male)
    gw, ew = words(g_al), words(e_al)
    fig, ax = plt.subplots(2, 1, figsize=(11, 4.6))
    for a, (t, s, ws, lab) in zip(ax, [(te, se, ew, 'English'), (tg, sg, gw, 'Gibberish')]):
        a.plot(t, s - np.nanmedian(s), '.', ms=2.5, color='#1f5fa8' if lab == 'English' else '#b8461f')
        a.set_ylim(-9, 11); a.set_ylabel(lab + '\n(semitones)', fontsize=8); a.grid(alpha=.25)
        for k, (w, s0, e0) in enumerate(ws):
            c = 'C%d' % ((k if lab == 'English' else (gmap[k]['src'] if gmap[k].get('src') is not None else 9)) % 10)
            a.axvspan(s0, e0, color=c, alpha=.10); a.text((s0 + e0) / 2, 9.6, w, ha='center', fontsize=7, rotation=0)
    ax[0].set_title(title, fontsize=9); ax[1].set_xlabel('seconds (same colour = same meaning)')
    fig.tight_layout(); fig.savefig(path_png, dpi=110); plt.close(fig)
