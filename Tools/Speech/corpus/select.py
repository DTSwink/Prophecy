"""Pick a balanced starter bank from the corpus that fits ~one month of ElevenLabs credits."""
import json, gzip, random, re, collections
rng = random.Random(5)
sc = [json.loads(l) for l in gzip.open('/home/claude/corpus/speech_corpus_v1.jsonl.gz', 'rt')]
BUDGET = 30000
cost = lambda s: sum(len(l['tags']) + 1 + len(l['text']) for l in s['lines'])
def ok(s):
    n = len(s['lines'])
    return 5 <= n <= 12 and max(len(l['text']) for l in s['lines']) <= 200 and all(re.sub(r'\[[^\]]*\]|\W', '', l['text']) for l in s['lines'])
orig = [s for s in sc if s['source'] == 'Original']
pool = [s for s in sc if s['source'] != 'Original' and ok(s)]
share = {'small_talk': .30, 'storytelling': .17, 'bargaining': .13, 'dispute': .14, 'banter': .14, 'emotional': .12}
picked = list(orig)
left = BUDGET - sum(cost(s) for s in orig)
by = collections.defaultdict(list)
for s in pool: by[s['category']].append(s)
for k in by: rng.shuffle(by[k])
for cat, frac in share.items():
    room = left * frac
    # rotate speaker counts 2/3/4 inside each category
    queues = {n: [s for s in by[cat] if s['n_speakers'] == n] for n in (2, 3, 4)}
    order = [2, 3, 4] if cat != 'bargaining' else [2, 2, 2]
    i = 0
    while room > 0 and any(queues.values()):
        n = order[i % len(order)]; i += 1
        if not queues.get(n): continue
        s = queues[n].pop()
        if cost(s) > room + 200: continue
        picked.append(s); room -= cost(s)
total = sum(cost(s) for s in picked)
stats = dict(scenes=len(picked), lines=sum(len(s['lines']) for s in picked), characters=total,
             est_minutes=round(total / 900, 1), by_category=collections.Counter(s['category'] for s in picked),
             by_speakers=collections.Counter(s['n_speakers'] for s in picked), by_source=collections.Counter(s['source'] for s in picked))
print(json.dumps(stats, indent=1, default=dict))
json.dump(dict(stats=stats, scenes=picked), open('/home/claude/corpus/starter_bank_v1.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
