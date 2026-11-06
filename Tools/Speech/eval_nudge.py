"""Run nudge configs on the apple scene ml2 base and print objective scores (cloud test harness)."""
import json, sys, os, numpy as np, analyze as A, nudge as N
U = '/mnt/user-data/uploads/Prophecy/Saved/Speech/'
S = '/tmp/claude-0/-home-claude/0fe64c57-808d-5039-ab94-85f914c99794/scratchpad/nudge/'
B = json.load(open('/mnt/user-data/outputs/speech/batches/ab_apples_v3_ml2.json'))
L = [f'{i:02d}_{s}' for i, s in enumerate(['S1', 'S2'] * 4)]
def run(name, kw, base='ab_apples_v3_ml2/ml2_fr', lines=range(8), plots=()):
    os.makedirs(S + name, exist_ok=True); rows = []
    for i in lines:
        n = L[i]; male = n.endswith('S1')
        g = json.load(open(U + f'{base}/{n}.json')); e = json.load(open(U + f'ab_apples_en/v3_en/{n}.json'))
        gp, ep = U + f'{base}/{n}.mp3', U + f'ab_apples_en/v3_en/{n}.mp3'
        out = S + f'{name}/{n}.wav'
        N.nudge(gp, g['alignment'], B['lines'][i]['words'], ep, e['alignment'], male, out, **kw)
        snd = A.load(out); es = A.load(ep)
        r = A.damage(snd, male); r['dnsmos_sig'], r['dnsmos_ovr'] = A.dnsmos(snd)
        r.update(A.melody(snd, g['alignment'], B['lines'][i]['words'], es, e['alignment'], male)); rows.append(r)
        if i in plots: A.plot(S + f'plot_{name}_{n}.png', snd, g['alignment'], B['lines'][i]['words'], es, e['alignment'], male, title=f"{name} line {i+1}: {B['lines'][i]['english']}")
    m = {k: round(float(np.nanmean([r[k] for r in rows])), 3) for k in rows[0]}
    print(name, m, flush=True); return m
if __name__ == '__main__':
    cfgs = json.loads(sys.argv[1])
    for name, kw in cfgs.items(): run(name, kw, plots=(1, 2))
