"""Trim primers / split concatenated takes on the ElevenLabs alignment (cut in the quietest 10 ms between the primer and
the line), then language-ID the remaining line with Whisper-small.
usage: python -I accent_eval.py <exp dir with id.mp3 + id.json> <out dir>"""
import sys, os, json, glob, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from accent_lid import load, lid
SR = 16000

def quiet_point(x, t0, t1):
    a, b = int(max(0, t0) * SR), int(min(len(x) / SR, t1) * SR)
    if b - a < 320: return 0.5 * (t0 + t1)
    hop = 160; e = [np.sqrt(np.mean(x[i:i + 320] ** 2)) for i in range(a, b - 320, hop)]
    return (a + int(np.argmin(e)) * hop + 160) / SR

def span_of(al, sub, start=0):
    txt = ''.join(al['characters']); i = txt.find(sub, start)
    if i < 0: return None
    return i, i + len(sub) - 1

def cuts(rec, x):
    """[(label, t_start, t_end)] of the line(s) in this take"""
    al = rec['alignment']; S, E = al['character_start_times_seconds'], al['character_end_times_seconds']
    dur = len(x) / SR; txt = ''.join(al['characters'])
    segs = rec.get('segments')
    if segs:   # concatenated lines: cut between consecutive line texts
        spans = []; pos = 0
        for s in segs:
            sp = span_of(al, s, pos); spans.append(sp); pos = sp[1] + 1
        c = [quiet_point(x, E[span_of(al, rec['prime'])[1]] - 0.05, S[spans[0][0]] + 0.05) if rec.get('prime') else 0.0]
        for k in range(1, len(spans)):   # the tag of line k sits between the two texts: cut just before it
            c.append(quiet_point(x, E[spans[k - 1][1]] - 0.02, S[spans[k][0]] + 0.05))
        c.append(dur); labs = rec['line'].split(',')
        return [(labs[k], c[k], c[k + 1]) for k in range(len(spans))]
    if rec.get('prime'):
        i, j = span_of(al, rec['prime'])
        nxt = next(k for k in range(j + 1, len(txt)) if not txt[k].isspace())
        return [(rec['line'], quiet_point(x, E[j] - 0.05, S[nxt] + 0.12), dur)]
    return [(rec['line'], 0.0, dur)]

def main(src, out):
    os.makedirs(out, exist_ok=True); rows = []
    for js in sorted(glob.glob(os.path.join(src, '*.json'))):
        rec = json.load(open(js, encoding='utf8'))
        if 'alignment' not in rec or not rec['alignment']: print(rec['id'], 'FAILED', rec.get('error', '')[:120]); continue
        mp3 = js[:-5] + '.mp3'; x = load(mp3)
        for lab, a, b in cuts(rec, x):
            seg = x[int(a * SR):int(b * SR)]
            name = f"{rec['id']}" + (f"__{lab}" if rec.get('segments') else '')
            wav = os.path.join(out, name + '.wav')
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{a:.3f}', '-t', f'{b - a:.3f}', '-i', mp3, '-af', 'afade=t=in:d=0.015',
                            wav], check=True)
            n = int(2.5 * SR); W = [float(lid(seg[k:k + n])['fr']) for k in range(0, max(1, len(seg) - n // 2), n // 2)]
            P = lid(seg); top = sorted(P.items(), key=lambda kv: -kv[1])[:3]
            rows.append(dict(id=name, line=lab, cut=round(a, 3), dur=round(b - a, 2), fr=round(float(P['fr']), 3), frmin=round(min(W), 3),
                             top=' '.join(f'{c}:{v:.2f}' for c, v in top)))
            print(f"{name:28s} cut {a:5.2f}s dur {b - a:4.2f}s  fr {P['fr']:.2f} min2.5s {min(W):.2f} | {rows[-1]['top']}", flush=True)
    json.dump(rows, open(os.path.join(out, 'scores.json'), 'w'), indent=1)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
