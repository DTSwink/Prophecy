"""Context annotation for ElevenLabs: scene category + per-line emotion, intensity (0-3) and delivery tags.

Policy (user, Nov 4): the first mockup was very emotional; casual talk must be watered down.
- Intensity is capped by scene category: small_talk 1, storytelling 1 (2 on clear peaks), bargaining 1, banter 2,
  emotional 2 (3 only for clear panic/grief), dispute 3.
- Intensity 0 -> no tag (default for neutral lines and for about half the mild lines in calm scenes).
- Emotion comes from the dataset label when present (MELD every line, Friends partly), else from text cues.
"""
import hashlib, re

LEX = {
    'anger': r"\b(shut up|damn|hell|idiot|stupid|how dare|what the|get out|i hate|liar|furious|ridiculous)\b",
    'joy': r"\b(haha|ha ha|hehe|yay|awesome|great|wonderful|love it|amazing|congratulations|fantastic|perfect|cool)\b",
    'sadness': r"\b(i'?m sorry|i miss|sad|died|dead|cry|crying|lost|alone|tears|funeral)\b",
    'fear': r"\b(oh no|help|scared|afraid|careful|run|watch out|terrified|please don'?t)\b",
    'surprise': r"\b(what\?|really\?|oh my god|no way|wow|whoa|seriously\?|are you serious)\b",
    'disgust': r"\b(gross|ew+|disgusting|yuck)\b",
}
LEXC = {k: re.compile(v, re.I) for k, v in LEX.items()}
TAGS = {
    'joy': {1: ['warmly', 'amused', 'cheerfully'], 2: ['excited', 'happily'], 3: ['excited']},
    'surprise': {1: ['curious'], 2: ['surprised'], 3: ['gasps']},
    'anger': {1: ['annoyed', 'irritated'], 2: ['angry', 'frustrated'], 3: ['shouts']},
    'sadness': {1: ['softly', 'wistful'], 2: ['sad'], 3: ['sorrowful']},
    'fear': {1: ['hesitant'], 2: ['nervous', 'worried'], 3: ['panicked']},
    'disgust': {1: ['dismissive'], 2: ['disgusted'], 3: ['disgusted']},
    'powerful': {1: ['confident'], 2: ['firmly'], 3: ['firmly']},
    'peaceful': {1: ['calmly', 'gently'], 2: ['calmly'], 3: ['calmly']},
}
CAP = {'small_talk': 1, 'storytelling': 1, 'bargaining': 1, 'banter': 2, 'emotional': 2, 'dispute': 3}

def h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

def guess_emotion(t):
    for k in ('anger', 'fear', 'sadness', 'surprise', 'disgust', 'joy'):
        if LEXC[k].search(t): return k
    return 'neutral'

def categorize(scene):
    src = scene['source']
    if src == 'DealOrNoDeal': return 'bargaining'
    emos = [l['emotion'] for l in scene['lines']]
    ang = emos.count('anger') + emos.count('disgust')
    sad = emos.count('sadness') + emos.count('fear')
    joy = emos.count('joy') + emos.count('surprise')
    longest = max(len(l['en']) for l in scene['lines'])
    if ang >= 2: return 'dispute'
    if sad >= 2: return 'emotional'
    if longest > 200 or (src == 'CRD3' and longest > 140): return 'storytelling'
    if joy >= 3: return 'banter'
    return 'small_talk'

def annotate(scene):
    labelled = any(l.get('emotion_src') for l in scene['lines'])
    for l in scene['lines']:
        e = l.get('emotion_src') or guess_emotion(l['en'])
        l['emotion'] = e; l['labelled'] = bool(l.get('emotion_src'))
    cat = scene.get('category') or categorize(scene)
    scene['category'] = cat
    cap = CAP[cat]
    for i, l in enumerate(scene['lines']):
        t, e = l['en'], l['emotion']
        if t == '[laughs]':
            l.update(intensity=1, tags='[laughs]', en='Ha ha ha.'); continue
        excl = t.count('!'); caps = len(re.findall(r'\b[A-Z]{3,}\b', t))
        if e == 'neutral':
            inten = 0
        else:
            inten = 1 + (1 if excl else 0) + (1 if (caps or excl >= 2) else 0)
            if not l['labelled']: inten = min(inten, 2)       # text cues alone never reach the top
        peak = cat == 'storytelling' and (excl >= 2 or caps) and e in ('fear', 'anger', 'surprise')
        inten = min(inten, cap + (1 if peak else 0))
        if e == 'sadness' and cat == 'emotional' and re.search(r'\b(died|dead|gone|never)\b', t, re.I): inten = max(inten, 2)
        r = h(scene.get('ref', '') + str(i) + t)
        if inten == 1 and cat in ('small_talk', 'storytelling', 'bargaining') and r % 2: inten = 0
        tags = []
        if inten:
            opts = TAGS.get(e, {}).get(inten)
            if opts: tags.append(opts[r % len(opts)])
        if re.search(r'\b(ha ?ha|hehe|lol)\b', t, re.I): tags = ['laughs' if inten >= 2 else 'chuckles']
        elif re.match(r'(ugh|oh well|sigh)\b', t, re.I): tags = ['sighs'] + tags[:0]
        l['intensity'] = inten
        l['tags'] = ' '.join(f'[{x}]' for x in tags)
    scene['energy'] = 'high' if cat == 'dispute' or max(l['intensity'] for l in scene['lines']) >= 3 else \
                      ('low' if cat in ('small_talk', 'storytelling', 'bargaining') else 'medium')
    return scene
