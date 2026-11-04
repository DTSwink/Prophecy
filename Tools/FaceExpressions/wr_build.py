"""Build cheap wrinkle textures from Ada's MetaHuman wrinkle maps (shared MetaHuman head UVs).

Outputs (out/wrinkles):
  T_Face_WrinkleDetail.png   1024 RGBA: RG = layer1 (stretch: wm1+wm3) detail normal XY, BA = layer2 (compress: wm2) XY
  T_Face_WrinkleMasks_0..3   256 RGBA: per (expression, layer) weight masks, channel table in wrinkle_layout.json
  preview/<expr>_N.png       full normal maps (Ada base + detail at weight 1) for offline preview renders only
Detail = slope difference (wrinkle map minus Ada base normal), so it carries no pores/identity of Ada.
"""
import numpy as np, json, os
from PIL import Image
F = '/home/claude/face/'; M = F + 'dnacal/data/'; OUT = F + 'out/wrinkles/'
os.makedirs(OUT + 'preview', exist_ok=True)
RES, MRES = 1024, 256

def nrm(f):
    a = np.asarray(Image.open(M + 'maps/' + f).convert('RGB'), np.float64) / 255 * 2 - 1
    bad = (np.linalg.norm(a, axis=2) < 0.5) | (a[..., 2] < 0.05)  # empty texels outside UV islands
    a[bad] = (0, 0, 1)
    return a / np.linalg.norm(a, axis=2, keepdims=True)
slopes = lambda n: np.stack([-n[..., 0] / n[..., 2], -n[..., 1] / n[..., 2]], -1)
base = nrm('head_normal_map.tga'); sb = slopes(base)
D = {k: slopes(nrm(f'head_{k}_normal_map.tga')) - sb for k in ('wm1', 'wm2', 'wm3')}
W = json.load(open(F + 'anim_weights.json'))
mask_cache = {}
def mask(name, res):
    k = (name, res)
    if k not in mask_cache:
        mask_cache[k] = np.asarray(Image.open(M + f'masks/{name}_msk.tga').convert('L').resize((res, res), Image.BILINEAR), np.float64) / 255
    return mask_cache[k]
LAYER = {'wm1': 1, 'wm3': 1, 'wm2': 2}

# per (expression, layer) weight fields
fields = {}
for e, ws in W.items():
    for key, w in ws.items():
        nm, mp = key.split('|')
        if mp not in LAYER: continue  # colour maps handled later (flush)
        fields.setdefault((e, LAYER[mp]), {'hi': 0, 'lo': 0})
        fields[(e, LAYER[mp])]['hi'] = fields[(e, LAYER[mp])]['hi'] + w * mask(nm, RES)
        fields[(e, LAYER[mp])]['lo'] = fields[(e, LAYER[mp])]['lo'] + w * mask(nm, MRES)
# expressions whose wrinkles are re-used from other channels (handled by material params)
ALIASES = {'Dead': {'Blink_L': 1.0, 'Blink_R': 1.0}, 'LookDown': {'Blink_L': 0.7, 'Blink_R': 0.7}}
ORDER = ['Blink_L', 'Blink_R', 'JawOpen', 'Effort', 'Pain', 'Shout', 'Anger', 'Fear', 'Grin']
channels = [(e, l) for e in ORDER for l in (1, 2) if (e, l) in fields and fields[(e, l)]['lo'].max() > 0.02]
print('channels', len(channels), channels)

# layer-1 detail: energy-weighted merge of wm1 and wm3 (measured conflict ~3% of total)
A = {k: np.zeros((RES, RES)) for k in D}
for e, ws in W.items():
    acc = {k: np.zeros((RES, RES)) for k in D}
    for key, w in ws.items():
        nm, mp = key.split('|')
        if mp in acc: acc[mp] += w * mask(nm, RES)
    for k in D: A[k] = np.maximum(A[k], np.clip(acc[k], 0, 1))
E1 = A['wm1'] * np.linalg.norm(D['wm1'], axis=2) + 1e-6; E3 = A['wm3'] * np.linalg.norm(D['wm3'], axis=2) + 1e-6
L1 = (D['wm1'] * E1[..., None] + D['wm3'] * E3[..., None]) / (E1 + E3)[..., None]
L2 = D['wm2'].copy()
# zero detail outside any used mask to avoid stray noise from map differences
used1 = np.clip(sum(fields[c]['hi'] for c in channels if c[1] == 1), 0, 1)
used2 = np.clip(sum(fields[c]['hi'] for c in channels if c[1] == 2), 0, 1)
L1 *= np.clip(used1 * 4, 0, 1)[..., None]; L2 *= np.clip(used2 * 4, 0, 1)[..., None]
def enc(s):
    n = np.concatenate([-s, np.ones(s.shape[:2] + (1,))], -1); n /= np.linalg.norm(n, axis=2, keepdims=True)
    return np.clip(np.round((n[..., :2] * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8)
det = np.concatenate([enc(L1), enc(L2)], -1)
Image.fromarray(det, 'RGBA').save(OUT + 'T_Face_WrinkleDetail.png')

# masks packed 4 per texture
ntex = (len(channels) + 3) // 4
table = []
for t in range(ntex):
    arr = np.zeros((MRES, MRES, 4), np.uint8)
    for c in range(4):
        i = t * 4 + c
        if i < len(channels):
            arr[..., c] = np.round(np.clip(fields[channels[i]]['lo'], 0, 1) * 255)
            table.append(dict(texture=f'T_Face_WrinkleMasks_{t}', channel='RGBA'[c], expression=channels[i][0], layer=channels[i][1]))
    Image.fromarray(arr, 'RGBA').save(OUT + f'T_Face_WrinkleMasks_{t}.png')
json.dump(dict(channels=table, aliases=ALIASES, detail='T_Face_WrinkleDetail: RG=layer1 (stretch) normal XY, BA=layer2 (compress) normal XY, DirectX green like MetaHuman source',
               note='Layer weight = clamp(sum over channels of param[expression]*mask, 0, 1); param[Blink_L] includes Dead + 0.7*LookDown (aliases)'),
          open(OUT + 'wrinkle_layout.json', 'w'), indent=1)

# preview normals (Ada base + full detail), per expression, OpenGL green for Blender
def decode(x):
    x = x.astype(np.float64) / 255 * 2 - 1; z = np.sqrt(np.clip(1 - (x ** 2).sum(-1), 0, 1)); n = np.concatenate([x, z[..., None]], -1)
    return slopes(n)
d1, d2 = decode(det[..., :2]), decode(det[..., 2:])
up = lambda m: np.asarray(Image.fromarray(np.round(np.clip(m, 0, 1) * 255).astype(np.uint8)).resize((RES, RES), Image.BILINEAR), np.float64) / 255
for e in ORDER + ['Dead', 'LookDown', 'Neutral']:
    params = {e: 1.0}
    for a, mp in ALIASES.items():
        if a in params:
            for k, v in mp.items(): params[k] = params.get(k, 0) + v
    w1 = np.zeros((RES, RES)); w2 = np.zeros((RES, RES))
    for (ce, l) in channels:
        if ce in params:
            m = up(fields[(ce, l)]['lo']) * params[ce]
            if l == 1: w1 += m
            else: w2 += m
    s = sb + np.clip(w1, 0, 1)[..., None] * d1 + np.clip(w2, 0, 1)[..., None] * d2
    n = np.concatenate([-s, np.ones((RES, RES, 1))], -1); n /= np.linalg.norm(n, axis=2, keepdims=True)
    n[..., 1] *= -1  # DirectX -> OpenGL for Blender
    Image.fromarray(np.round((n * 0.5 + 0.5) * 255).astype(np.uint8), 'RGB').save(OUT + f'preview/{e}_N.png')
print('done', ntex, 'mask textures')
