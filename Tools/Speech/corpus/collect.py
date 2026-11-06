"""Collect varied 2-4 speaker dialogue scenes from open dialogue datasets into one JSONL.

Sources (raw files in raw/):
  MELD (declare-lab/MELD, GPL-3.0): multi-party TV dialogues, every line emotion-labelled (7 classes).
  Friends transcripts (emorynlp/character-mining): multi-party scenes, part emotion-labelled (Willcox wheel).
  CRD3 (Critical Role D&D, CC BY-SA 4.0): fantasy storytelling, GM narration + players.
  Deal or No Deal (facebookresearch/end-to-end-negotiator, CC BY-NC): 2-party bargaining.
Scene = window of 4..16 consecutive lines with 2..4 distinct speakers. English is only a meaning/emotion scaffold
("trame de fond"); it is never spoken: everything is relexified into the invented language afterwards.
"""
import csv, glob, json, os, random, re, hashlib, unicodedata
from collections import Counter

RAW = '/home/claude/corpus/raw/'
OUT = '/home/claude/corpus/scenes_raw.jsonl'
rng = random.Random(11)

F = {'Monica': 'f', 'Rachel': 'f', 'Phoebe': 'f', 'Janice': 'f', 'Carol': 'f', 'Susan': 'f', 'Emily': 'f', 'Mona': 'f',
     'Ross': 'm', 'Chandler': 'm', 'Joey': 'm', 'Gunther': 'm', 'Richard': 'm', 'Mike': 'm', 'Paul': 'm', 'Mr. Geller': 'm',
     'Mrs. Geller': 'f', 'Frank': 'm', 'Ben': 'm', 'Pete': 'm', 'Tag': 'm', 'Charlie': 'f', 'Kathy': 'f', 'Julie': 'f',
     'Barry': 'm', 'Ursula': 'f', 'Estelle': 'f', 'Amy': 'f', 'Elizabeth': 'f', 'Gary': 'm', 'Jill': 'f', 'Erica': 'f',
     'MATT': 'm', 'LAURA': 'f', 'MARISHA': 'f', 'LIAM': 'm', 'TALIESIN': 'm', 'SAM': 'm', 'TRAVIS': 'm', 'ORION': 'm',
     'ASHLEY': 'f', 'ZAC': 'm', 'MARK': 'm', 'MARY': 'f', 'FELICIA': 'f', 'WIL': 'm', 'PATRICK': 'm', 'KIT': 'f', 'CHRIS': 'm'}

def gender(name):
    first = name.split()[0] if name else ''
    return F.get(name) or F.get(first) or F.get(first.capitalize()) or 'u'

def clean(t):
    t = unicodedata.normalize('NFKC', t or '')
    t = t.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').replace('…', '...')
    t = t.replace('Â', '').replace('\u0092', "'").replace('\u0085', '...').replace('\x96', '-').replace('\x97', '-')
    t = re.sub(r'\([^)]*\)', ' ', t)          # stage directions
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def windows(lines, minl=4, maxl=16, maxspk=None):
    """Split a long speaker sequence into scenes with 2..4 distinct speakers (target count varies per window)."""
    out, i, n = [], 0, len(lines)
    fixed = maxspk
    while i < n:
        maxspk = fixed or rng.choice([2, 2, 3, 3, 4])
        spk, j = set(), i
        while j < n and len(lines[j:j + 1]) and (len(spk | {lines[j]['spk']}) <= maxspk) and j - i < maxl:
            spk.add(lines[j]['spk']); j += 1
        # prefer ending a window on a natural boundary: last line with ?,! or . and a reasonable size
        if j - i >= minl and len(spk) >= 2:
            out.append(lines[i:j])
        i = j if j > i else i + 1
    return out

EMO_MELD = {'neutral': 'neutral', 'joy': 'joy', 'surprise': 'surprise', 'anger': 'anger', 'sadness': 'sadness', 'fear': 'fear', 'disgust': 'disgust'}
EMO_FR = {'Neutral': 'neutral', 'Joyful': 'joy', 'Peaceful': 'peaceful', 'Powerful': 'powerful', 'Scared': 'fear', 'Mad': 'anger', 'Sad': 'sadness'}

scenes = []
seen_lines = set()

# ---------------- MELD ----------------
dialogs = {}
for split in ('train', 'dev', 'test'):
    with open(RAW + f'meld_{split}.csv', encoding='utf-8', errors='replace') as fh:
        for r in csv.DictReader(fh):
            dialogs.setdefault((split, int(r['Dialogue_ID'])), []).append(r)
for (split, did), rows in sorted(dialogs.items()):
    rows.sort(key=lambda r: int(r['Utterance_ID']))
    lines = [dict(spk=r['Speaker'], en=clean(r['Utterance']), emotion=EMO_MELD.get(r['Emotion'], 'neutral')) for r in rows]
    lines = [l for l in lines if l['en']]
    for w in windows(lines, minl=4):
        scenes.append(dict(source='MELD', ref=f'{split}-{did}', lines=w))
        for l in w: seen_lines.add(l['en'].lower())
n_meld = len(scenes)

# ---------------- Friends transcripts ----------------
for f in sorted(glob.glob(RAW + 'friends_*.json')):
    d = json.load(open(f))
    for ep in d['episodes']:
        for sc in ep['scenes']:
            lines = []
            for u in sc['utterances']:
                sp = u.get('speakers') or []
                t = clean(u.get('transcript'))
                if len(sp) != 1 or not t: continue
                emo = u.get('emotion')
                e = None
                if emo:
                    lab = emo[0] if isinstance(emo, list) else emo
                    if isinstance(lab, list): lab = lab[0]
                    e = EMO_FR.get(lab)
                lines.append(dict(spk=sp[0], en=t, emotion=e))
            for w in windows(lines):
                dup = sum(1 for l in w if l['en'].lower() in seen_lines)
                if dup > len(w) * 0.3: continue
                scenes.append(dict(source='Friends', ref=sc['scene_id'], lines=w))
n_friends = len(scenes) - n_meld

# ---------------- CRD3 (fantasy storytelling) ----------------
crd = []
for f in sorted(glob.glob(RAW + 'crd3/data/cleaned data/*.json')):
    d = json.load(open(f))
    lines = []
    for t in d['TURNS']:
        if len(t['NAMES']) != 1 or t['NAMES'][0] in ('ALL', 'AUDIENCE'): continue
        txt = clean(' '.join(t['UTTERANCES']))
        if not txt: continue
        if re.fullmatch(r'(laughter|laughs|laughing)\.?', txt, re.I): txt = '[laughs]'
        lines.append(dict(spk=t['NAMES'][0], en=txt, emotion=None))
    ws = windows(lines, minl=5, maxl=14)
    mech = re.compile(r'\b(roll|rolled|d20|d6|d8|d10|d12|natural|damage|hit points|initiative|advantage|disadvantage|saving throw|attack|AC|spell slot|bonus action|perception|check)\b', re.I)
    num = re.compile(r'^(\d+|[a-z]+teen|twenty|thirty|five|ten|eleven|twelve)[.!?]?$', re.I)
    ws = [w for w in ws if sum(1 for l in w if mech.search(l['en']) or num.match(l['en'])) <= len(w) * 0.2
          and max(len(l['en']) for l in w) < 700]
    rng.shuffle(ws)
    for w in ws[:14]:  # sample per episode to keep variety across the whole campaign
        crd.append(dict(source='CRD3', ref=os.path.basename(f)[:-5], lines=w))
scenes += crd

# ---------------- Deal or No Deal (bargaining) ----------------
dnd, seen_d = [], set()
for line in open(RAW + 'dnd_train.txt', encoding='utf8'):
    m = re.search(r'<dialogue>(.*?)</dialogue>', line)
    if not m: continue
    turns = [t.strip() for t in m.group(1).split('<eos>')]
    lines = []
    for t in turns:
        mm = re.match(r'(YOU|THEM):\s*(.*)', t)
        if not mm or '<selection>' in mm.group(2): continue
        txt = mm.group(2).strip()
        txt = re.sub(r'\s+([.,!?])', r'\1', txt)
        txt = txt[:1].upper() + txt[1:]
        lines.append(dict(spk='Buyer' if mm.group(1) == 'YOU' else 'Seller', en=txt, emotion=None))
    key = ' '.join(l['en'] for l in lines)
    if len(lines) >= 4 and key not in seen_d:
        seen_d.add(key); dnd.append(dict(source='DealOrNoDeal', ref=f'dnd{len(dnd)}', lines=lines))
rng.shuffle(dnd)
scenes += dnd[:450]

# ---------------- finalize ----------------
out = []
for i, s in enumerate(scenes):
    spk_order = []
    for l in s['lines']:
        if l['spk'] not in spk_order: spk_order.append(l['spk'])
    s['speakers'] = [dict(id=f'S{k + 1}', name_en=n, gender=gender(n)) for k, n in enumerate(spk_order)]
    idmap = {n: f'S{k + 1}' for k, n in enumerate(spk_order)}
    s['lines'] = [dict(spk=idmap[l['spk']], en=l['en'], emotion_src=l['emotion']) for l in s['lines']]
    s['n_speakers'] = len(spk_order)
    out.append(s)
with open(OUT, 'w', encoding='utf8') as fh:
    for s in out: fh.write(json.dumps(s, ensure_ascii=False) + '\n')
c = Counter((s['source'], s['n_speakers']) for s in out)
print('MELD', n_meld, 'Friends', n_friends, 'CRD3', len(crd), 'DnD', min(450, len(dnd)))
print(sorted(c.items()))
print('lines', sum(len(s['lines']) for s in out))
