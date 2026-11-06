"""Score real-language takes of the apple scene against the English take and mix one listening file per take."""
import json, sys, numpy as np, analyze as A, scene_mix as M
U = '/mnt/user-data/uploads/Prophecy/Saved/Speech/'
OUT = '/mnt/user-data/outputs/audio/'
L = [f'{i:02d}_{s}' for i, s in enumerate(['S1', 'S2'] * 4)]
def score(d, batch):
    rows = []
    for i, n in enumerate(L):
        male = n.endswith('S1'); g = json.load(open(U + f'{d}/{n}.json')); e = json.load(open(U + f'ab_apples_en/v3_en/{n}.json'))
        gs = A.load(U + f'{d}/{n}.mp3'); es = A.load(U + f'ab_apples_en/v3_en/{n}.mp3')
        r = A.melody(gs, g['alignment'], batch['lines'][i]['words'], es, e['alignment'], male); r['dnsmos_ovr'] = A.dnsmos(gs)[1]; r['dur'] = gs.duration; rows.append(r)
    return {k: (round(float(np.nanmean([r[k] for r in rows])), 2) if k != 'dur' else round(sum(r[k] for r in rows), 1)) for k in rows[0]}
if __name__ == '__main__':
    res = {}
    for lang in sys.argv[1:]:
        b = json.load(open(f'/mnt/user-data/outputs/speech/batches/ab_apples_{lang}.json'))
        for v in b['variants']:
            d = f'ab_apples_{lang}/{v["id"]}'
            M.mix([U + f'{d}/{n}.mp3' for n in L], OUT + f'apples_{lang}_{v["id"].split("_")[0]}.mp3')
            res[f'{lang} {v["id"]}'] = score(d, b); print(f'{lang} {v["id"]}', res[f'{lang} {v["id"]}'], flush=True)
    json.dump(res, open('/tmp/claude-0/-home-claude/0fe64c57-808d-5039-ab94-85f914c99794/scratchpad/lang_scores.json', 'w'), indent=1)
