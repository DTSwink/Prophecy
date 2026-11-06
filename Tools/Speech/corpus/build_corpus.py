"""Annotate + translate every scene into the invented language and write the corpus files."""
import json, re, sys, time, collections, gzip
sys.path.insert(0, '/home/claude/speech'); sys.path.insert(0, '/home/claude/corpus')
from annotate import annotate
from originals import ORIGINALS
from lang2 import Lang2

TAG_INT = {'shouts': 3, 'panicked': 3, 'sorrowful': 3, 'angry': 2, 'excited': 2, 'laughs': 2, 'sad': 2, 'nervous': 2, 'worried': 2,
           'surprised': 2, 'firmly': 2, 'disgusted': 2}
TAG_EMO = {'angry': 'anger', 'annoyed': 'anger', 'shouts': 'anger', 'irritated': 'anger', 'frustrated': 'anger', 'sad': 'sadness',
           'softly': 'peaceful', 'sorrowful': 'sadness', 'nervous': 'fear', 'worried': 'fear', 'panicked': 'fear', 'hesitant': 'fear',
           'excited': 'joy', 'warmly': 'joy', 'amused': 'joy', 'laughs': 'joy', 'chuckles': 'joy', 'curious': 'surprise',
           'surprised': 'surprise', 'firmly': 'powerful', 'confident': 'powerful', 'calmly': 'peaceful', 'disgusted': 'disgust',
           'skeptical': 'disgust', 'sighs': 'sadness', 'thoughtful': 'peaceful', 'quietly': 'peaceful'}

t0 = time.time()
scenes = [json.loads(l) for l in open('/home/claude/corpus/scenes_raw.jsonl')]
scenes = [annotate(s) for s in scenes]
for k, o in enumerate(ORIGINALS):
    lines = []
    for spk, tags, en in o['lines']:
        names = re.findall(r'\[([^\]]+)\]', tags)
        inten = max([TAG_INT.get(n, 1) for n in names], default=0)
        emo = next((TAG_EMO[n] for n in names if n in TAG_EMO), 'neutral')
        lines.append(dict(spk=spk, en=en, emotion=emo, labelled=True, intensity=inten, tags=tags))
    scenes.insert(k, dict(source='Original', ref=f'orig{k:03d}', category=o['category'], mood=o['mood'],
                          speakers=[dict(id=i, name_en=r, gender=g) for i, g, r in o['speakers']], n_speakers=len(o['speakers']),
                          lines=lines, energy='high' if o['category'] == 'dispute' else ('medium' if o['category'] in ('banter', 'emotional') else 'low')))

L = Lang2()
# names: speaker names + capitalised tokens that appear mid-sentence often (people/places)
cnt = collections.Counter()
for s in scenes:
    for sp in s['speakers']:
        if s['source'] != 'Original' and sp['name_en'] not in ('Buyer', 'Seller'): L.known_names.add(sp['name_en'].split()[0].lower())
    for l in s['lines']:
        for m in re.finditer(r'(?<=[a-z,] )([A-Z][a-z]{2,})\b', l['en']): cnt[m.group(1).lower()] += 1
from wordfreq import zipf_frequency
for w, c in cnt.items():
    if c >= 3 and zipf_frequency(w, 'en') < 4.0: L.known_names.add(w)
print('known names', len(L.known_names), 'prep', round(time.time() - t0, 1), 's')

out = []
for n, s in enumerate(scenes):
    for sp in s['speakers']:
        base = sp['name_en'] if s['source'] != 'DealOrNoDeal' else f"{s['ref']}-{sp['name_en']}"
        sp['name'] = L.form(L.name_for(base.split()[0] if s['source'] != 'DealOrNoDeal' else base), cap=True)
    for l in s['lines']:
        l['text'] = L.translate(l['en'])
        l.pop('emotion_src', None)
    s['id'] = f"{s['source'][:3].upper()}{n:05d}"
    out.append(s)
    if n % 1000 == 0: print(n, round(time.time() - t0, 1), 's', flush=True)

with gzip.open('/home/claude/corpus/speech_corpus_v1.jsonl.gz', 'wt', encoding='utf8') as fh:
    for s in out: fh.write(json.dumps(s, ensure_ascii=False, separators=(',', ':')) + '\n')
json.dump(L.export(), open('/home/claude/corpus/lexicon_v2.json', 'w', encoding='utf8'), ensure_ascii=False)
json.dump({k: v for k, v in L.forms.items()}, open('/home/claude/corpus/forms_v2.json', 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
print('done', len(out), 'scenes', round(time.time() - t0, 1), 's; roots', len(L.roots), 'names', len(L.names), 'forms', len(L.forms))
