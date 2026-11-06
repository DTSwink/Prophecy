"""Prosody transfer: put the English performance (timing, melody, word stress) onto the gibberish recording of the
same line. Runs in the cloud (Praat via parselmouth), no ElevenLabs credits.

Inputs per line: English mp3 + its ElevenLabs character alignment, gibberish mp3 + alignment, and the word map
from lang3.translate_aligned (gibberish word -> English word index).
1. Word times from the character alignments. Anchors = matching word starts/ends (monotonic subset), plus the
   non-verbal lead-in ([chuckles]/[sighs] sound before the first word) and the line end.
2. Duration: PSOLA time warp so each gibberish word starts where its English word started, pauses land where the
   English pauses were (local factor clamped 0.6..1.6).
3. Melody: English F0 in semitones relative to the English speaker's median, re-centred on the gibberish voice's
   median, read through the time map (gaps in the English contour are interpolated); a little of the gibberish
   voice's own micro-melody is kept so it doesn't sound robotic. The lead-in keeps its own pitch.
4. Loudness: per-word gain so the words the English speaker stressed are louder (clamped +-6 dB, smoothed).
"""
import json, re, subprocess, sys
import numpy as np
import parselmouth
from parselmouth.praat import call

def load_sound(path):
    if path.lower().endswith('.mp3'):
        wav = path + '.tmp.wav'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', path, '-ac', '1', '-ar', '44100', wav], check=True)
        path = wav
    return parselmouth.Sound(path)

def words_from_alignment(al):
    """-> list of (word, start, end) for space-separated tokens, tags '[..]' marked with word=None."""
    cs, st, en = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
    out, cur = [], None
    for c, s, e in zip(cs, st, en):
        if c.isspace():
            if cur: out.append(cur); cur = None
            continue
        if cur is None: cur = [c, s, e]
        else: cur[0] += c; cur[2] = e
    if cur: out.append(cur)
    return [(None if w.startswith('[') and w.endswith(']') else w, s, e) for w, s, e in out]

def pitch_st(snd, floor, ceil):
    p = snd.to_pitch_ac(time_step=0.01, pitch_floor=floor, pitch_ceiling=ceil)
    f = p.selected_array['frequency']; t = p.xs()
    v = f > 0
    st = np.full_like(f, np.nan); st[v] = 12 * np.log2(f[v] / 100.0)
    return t, st

def interp_gaps(t, y, max_gap=None):
    v = ~np.isnan(y)
    if v.sum() < 2: return y
    return np.interp(t, t[v], y[v])

def lis_anchors(pairs):
    """Keep the largest subset of (g, e) pairs that increases in both g and e."""
    pairs = sorted(pairs)
    n = len(pairs); best = [1] * n; prev = [-1] * n
    for i in range(n):
        for j in range(i):
            if pairs[j][0] < pairs[i][0] - 1e-3 and pairs[j][1] < pairs[i][1] - 1e-3 and best[j] + 1 > best[i]:
                best[i] = best[j] + 1; prev[i] = j
    if not n: return []
    i = int(np.argmax(best)); out = []
    while i >= 0: out.append(pairs[i]); i = prev[i]
    return out[::-1]

def transfer(en_mp3, en_al, g_mp3, g_al, gwords, out_wav, male, detail=0.35, gain_db=6.0, report=None,
             melody=1.0, timing=1.0, phrase_only=False, clamp=(0.6, 1.6)):
    """Knobs (1 = copy the English fully, 0 = leave the gibberish take alone):
    melody      how far each pitch point moves from the gibberish voice's own melody towards the English one
    timing      how far word/pause times move from the take's own (globally rescaled) timing towards the English
    phrase_only only pauses/punctuation are aligned (words keep their natural internal rhythm)
    clamp       min/max local stretch factor; gain_db = max per-word loudness change"""
    floor, ceil = (60, 320) if male else (110, 520)
    en_snd, g_snd = load_sound(en_mp3), load_sound(g_mp3)
    T_en, T_g = en_snd.duration, g_snd.duration
    ew = [w for w in words_from_alignment(en_al) if w[0] is not None]
    gw_all = words_from_alignment(g_al)
    gw = [w for w in gw_all if w[0] is not None]
    assert len(gw) == len(gwords), (len(gw), len(gwords), [w[0] for w in gw], [x['g'] for x in gwords])
    # anchors
    pairs = [(0.0, 0.0)]
    lead_g, lead_e = gw[0][1], ew[0][1]
    pairs.append((lead_g, lead_e))
    # word starts always; word ends only before a real pause (>120 ms in either recording), otherwise tiny
    # inter-word gaps get extreme stretch factors and the warp sounds jerky
    for k, ((txt, s, e), m) in enumerate(zip(gw, gwords)):
        src = m.get('src')
        if src is None or src >= len(ew): continue
        g_gap = (gw[k + 1][1] - e) if k + 1 < len(gw) else 1.0
        e_gap = (ew[src + 1][1] - ew[src][2]) if src + 1 < len(ew) else 1.0
        after_pause = k == 0 or (s - gw[k - 1][2]) > 0.12 or re.search(r'[.,!?;:]$', gw[k - 1][0] or '')
        if not phrase_only or after_pause: pairs.append((s, ew[src][1]))
        if max(g_gap, e_gap) > 0.12: pairs.append((e, ew[src][2]))
    pairs.append((gw[-1][2], ew[-1][2]))
    pairs.append((T_g, T_en))
    anchors = lis_anchors(pairs)
    ag = np.array([a[0] for a in anchors]); ae = np.array([a[1] for a in anchors])
    ae = (1 - timing) * ag * (T_en / T_g) + timing * ae     # partial timing transfer
    # duration tier (piecewise constant factors, clamped)
    seg_f = np.clip(np.diff(ae) / np.maximum(np.diff(ag), 1e-3), *clamp)
    man = call(g_snd, 'To Manipulation', 0.01, floor, ceil)
    dt = call('Create DurationTier', 'dur', 0, T_g)
    for i, f in enumerate(seg_f):
        a, b = ag[i], ag[i + 1]
        if b - a < 0.004: continue
        call(dt, 'Add point', a + 0.001, float(f)); call(dt, 'Add point', b - 0.001, float(f))
    call([man, dt], 'Replace duration tier')
    out_of = lambda t: np.interp(t, ag, np.concatenate([[0], np.cumsum(np.diff(ag) * seg_f)]))   # gib time -> output time
    en_of = lambda t: np.interp(t, ag, ae)                                                          # gib time -> English time
    # pitch tier
    te, se = pitch_st(en_snd, *((60, 320) if male else (110, 520)))   # English reference voice range
    tg, sg = pitch_st(g_snd, floor, ceil)
    se_i = interp_gaps(te, se)
    m_en, m_g = np.nanmedian(se), np.nanmedian(sg)
    # gibberish micro-melody = its contour minus a 150 ms smoothed version
    sg_i = interp_gaps(tg, sg)
    k = 15; ker = np.ones(k) / k
    sg_s = np.convolve(np.pad(sg_i, k // 2, mode='edge'), ker, mode='valid')[:len(sg_i)]
    micro = np.nan_to_num(sg_i - sg_s)
    pt = call('Create PitchTier', 'pitch', 0, T_g)
    n_pts = 0
    for t, s, mic in zip(tg, sg, micro):
        if np.isnan(s): continue
        if t < lead_g - 0.02: target = s           # non-verbal lead-in keeps its own pitch
        else:
            full = m_g + (np.interp(en_of(t), te, se_i) - m_en) + detail * mic
            target = s + melody * (full - s)
        call(pt, 'Add point', float(t), float(100 * 2 ** (target / 12))); n_pts += 1
    call([man, pt], 'Replace pitch tier')
    out = call(man, 'Get resynthesis (overlap-add)')
    # per-word loudness from the English stress pattern
    y = out.values[0].copy(); sr = out.sampling_frequency
    def rms_db(snd_vals, sr_, a, b):
        seg = snd_vals[int(a * sr_):max(int(a * sr_) + 1, int(b * sr_))]
        return 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-6)
    ev = en_snd.values[0]
    e_db = {i: rms_db(ev, en_snd.sampling_frequency, s, e) for i, (_, s, e) in enumerate(ew)}
    o_spans = [(out_of(s), out_of(e)) for (_, s, e) in gw]
    o_db = [rms_db(y, sr, a, b) for a, b in o_spans]
    e_mean = np.mean(list(e_db.values())); o_mean = np.mean(o_db)
    env_t, env_g = [0.0], [0.0]
    for (a, b), m, od in zip(o_spans, gwords, o_db):
        if m.get('src') is None or m['src'] not in e_db: continue
        g = float(np.clip((e_db[m['src']] - e_mean) - (od - o_mean), -gain_db, gain_db))
        env_t += [a, b]; env_g += [g, g]
    env_t.append(len(y) / sr); env_g.append(0.0)
    tt = np.arange(len(y)) / sr
    gdb = np.interp(tt, env_t, env_g)
    w = int(0.06 * sr); gdb = np.convolve(np.pad(gdb, w // 2, mode='edge'), np.ones(w) / w, mode='valid')[:len(y)]
    y = y * 10 ** (gdb / 20)
    peak = np.max(np.abs(y))
    if peak > 0.98: y *= 0.98 / peak
    parselmouth.Sound(y, sampling_frequency=sr).save(out_wav, 'WAV')
    info = dict(T_en=round(T_en, 2), T_g=round(T_g, 2), T_out=round(len(y) / sr, 2), anchors=len(anchors), pitch_pts=n_pts,
                factor_min=round(float(seg_f.min()), 2), factor_max=round(float(seg_f.max()), 2),
                semitone_range_en=round(float(np.nanpercentile(se, 95) - np.nanpercentile(se, 5)), 1),
                semitone_range_gib=round(float(np.nanpercentile(sg, 95) - np.nanpercentile(sg, 5)), 1))
    if report is not None: report.append(info)
    return info
