"""French-flavoured invented language for Prophecy chatter.

Design (from research):
- Sounds first: French-like inventory and *uneven* frequencies (uvular R, l, s, t lead; nasal vowels an/on/in;
  front rounded u/eu; no diphthongs), plus a slight own identity (more v, j/zh, k than French).
- Syllable shapes weighted like spoken French (Wioland 1985: CV 56%, CCV 14%, CVC 14%, V 10%; ~80% open).
- Lexicon: generated roots + a few recurring suffixes/prefixes, Zipf-ranked; short, very frequent function words.
- Real words rejected (French + English, wordfreq) so it sounds French but never says anything.
- Relexification: an English script is mapped word-by-word, consistently, so repetition and rhythm look real.
- Each spelled word keeps (phoneme, char_start, char_end) spans -> exact visemes from ElevenLabs char timing.
Phoneme symbols (internal): a e E i o O u y 2(eu closed) 9(eu open) @(schwa) A~ O~ E~ | p b t d k g f v s z S Z m n N R l | j w H
"""
import random, re, json, hashlib
from wordfreq import zipf_frequency

V_W = {'a': 10, 'e': 8, 'i': 7, 'E': 6, 'u': 4, 'y': 3.5, 'o': 3.5, 'A~': 4, 'O~': 3, 'O': 2.5, 'E~': 2, '2': 1.5, '9': 1.0}
C_W = {'R': 10, 'l': 9, 's': 8, 't': 7.5, 'k': 7, 'v': 6, 'm': 6, 'd': 6, 'n': 5, 'p': 5, 'Z': 4, 'f': 3, 'b': 3, 'S': 2.5, 'z': 2.5, 'g': 1.5}
ONSET2 = {('p', 'R'): 3, ('t', 'R'): 4, ('k', 'R'): 3, ('b', 'R'): 2.5, ('d', 'R'): 2.5, ('g', 'R'): 1.5, ('f', 'R'): 2, ('v', 'R'): 1.5,
          ('p', 'l'): 2, ('k', 'l'): 2, ('b', 'l'): 2, ('f', 'l'): 1.5, ('g', 'l'): 1}
CODA_W = {'R': 6, 'l': 4, 's': 3, 'k': 2.5, 't': 2, 'm': 1.5, 'n': 1.5, 'Z': 1.5, 'v': 1.5, 'z': 0.8}
SYL_W = {'CV': 55, 'CCV': 14, 'CVC': 13, 'V': 10, 'CGV': 5, 'CCVC': 3}  # G = glide (j/w/H)
NASAL = {'A~', 'O~', 'E~'}
ROUND_FRONT = {'y', '2', '9'}

def wchoice(rng, d):
    ks = list(d); ws = [d[k] for k in ks]
    return rng.choices(ks, ws)[0]

def syllable(rng, first, last, shape=None):
    shape = shape or wchoice(rng, SYL_W)
    if first is False and shape == 'V': shape = 'CV'
    on = []
    if shape in ('CV', 'CVC', 'CGV'): on = [wchoice(rng, C_W)]
    elif shape in ('CCV', 'CCVC'): on = list(wchoice(rng, ONSET2))
    v = wchoice(rng, V_W)
    glide = []
    if shape == 'CGV':
        g = rng.choices(['j', 'w', 'H'], [5, 3, 1])[0]
        if g == 'w': v = rng.choice(['a', 'a', 'E~', 'e', 'i'])
        if g == 'H': v = 'i'
        if g == 'j' and v in ('i', 'y'): v = 'E'
        glide = [g]
    coda = []
    if shape in ('CVC', 'CCVC') and v not in NASAL:
        coda = [wchoice(rng, CODA_W)]
    if last is False and v in NASAL and rng.random() < 0.5:  # nasals mostly word-final or before consonant
        v = wchoice(rng, {k: w for k, w in V_W.items() if k not in NASAL})
    return on + glide + [v] + coda

def root(rng, nsyl):
    for _ in range(100):
        ph, prev = [], None
        for i in range(nsyl):
            s = syllable(rng, i == 0, i == nsyl - 1)
            if prev and s == prev: continue
            if ph and ph[-1] == s[0]: continue
            # nasal vowel must not be followed by a vowel or n/m (would denasalise in French reading)
            if ph and ph[-1] in NASAL and (s[0] in V_W or s[0] in ('n', 'm')): s = ['d'] + s if s[0] in V_W else ['t'] + s[1:]
            # no vowel hiatus inside a word
            if ph and ph[-1] in V_W and s[0] in V_W: s = [rng.choice(['l', 'R', 'v', 's'])] + s
            ph += s; prev = s
        if ph: return ph
    return ph

# ---------------- spelling (phoneme -> French graphemes, with spans) ----------------
FRONT = ('e', 'E', 'i', 'y', '@', 'E~', 'j', '2', '9')
def spell(ph, rng):
    """Return (text, spans) where spans = [(phoneme, start, end)] over text. Deterministic given rng."""
    out, spans = '', []
    n = len(ph)
    def nxt(i): return ph[i + 1] if i + 1 < n else None
    def prv(i): return ph[i - 1] if i > 0 else None
    for i, p in enumerate(ph):
        a, b = nxt(i), prv(i)
        final = a is None
        isV = lambda q: q in V_W
        g = None
        if p == 'a': g = 'a'
        elif p == 'i': g = 'i'
        elif p == 'u': g = 'ou'
        elif p == 'y': g = 'u'
        elif p == 'e':
            g = rng.choices(['é', 'er', 'ez'], [5, 3, 1])[0] if final else 'é'
        elif p == 'E':
            if b is None: g = 'ai' if a and not isV(a) else 'é'
            elif final: g = rng.choices(['ait', 'et', 'ais'], [4, 3, 2])[0]
            elif a and not isV(a) and (i + 2 >= n or not isV(ph[i + 2])): g = 'e'  # closed syllable
            else: g = 'è'
        elif p == 'o': g = rng.choices(['eau', 'ot', 'o'], [4, 3, 3])[0] if final else ('au' if rng.random() < 0.3 else 'o')
        elif p == 'O': g = 'o'
        elif p in ('2', '9'): g = rng.choices(['eu', 'eux'], [2, 1])[0] if final else 'eu'
        elif p == '@': g = 'e'
        elif p == 'A~': g = ('am' if a in ('p', 'b') else 'an') if not final else rng.choices(['an', 'ant', 'and'], [4, 2, 1])[0]
        elif p == 'O~': g = ('om' if a in ('p', 'b') else 'on') if not final else rng.choices(['on', 'ond'], [4, 1])[0]
        elif p == 'E~':
            if b == 'j': g = 'en'  # -ien
            else: g = ('im' if a in ('p', 'b') else ('ain' if rng.random() < 0.35 else 'in')) if not final else rng.choices(['in', 'ain'], [3, 2])[0]
        elif p == 'R': g = 'r' + ('e' if final and b in ('E', 'e', 'a', 'O', '2', '9') and b == 'E' else '')
        elif p == 'l': g = 'll' if (b and isV(b) and a and isV(a) and b == 'E') else 'l'
        elif p == 's': g = 'ss' if (b and isV(b) and b not in NASAL and a and isV(a)) else ('c' if (a in ('i', 'e', 'E') and rng.random() < 0.3 and b is None) else 's')
        elif p == 'z': g = 's' if (b and isV(b) and a and isV(a)) else 'z'
        elif p == 'k': g = 'qu' if a in FRONT else ('c' if not final else 'c')
        elif p == 'g': g = 'gu' if a in FRONT else 'g'
        elif p == 'Z': g = 'g' if a in ('e', 'E', 'i') else 'j'
        elif p == 'S': g = 'ch'
        elif p == 'N': g = 'gn'
        elif p == 'j': g = 'i' if (b and not isV(b)) else 'y'
        elif p == 'w':
            nv = a
            g = {'a': 'oi', 'E~': 'oin'}.get(nv)
            if g:  # 'oi'/'oin' already spells the vowel: consume it
                spans.append(('w', len(out), len(out) + 1)); spans.append((nv, len(out) + 1, len(out) + len(g)))
                out += g; ph[i + 1] = None; continue
            g = 'ou'
        elif p == 'H': g = 'u'
        elif p is None: continue
        else: g = p  # p b t d f v m n
        # word-final pronounced consonant needs a final -e in French spelling
        if final and p in ('t', 'd', 's', 'z', 'k', 'g', 'Z', 'S', 'v', 'm', 'n', 'p', 'b', 'N'):
            g = {'s': 'ce' if b in NASAL else 'sse', 'z': 'se', 'k': 'que', 'g': 'gue', 'Z': 'ge', 'S': 'che', 'N': 'gne'}.get(p, g + 'e')
        if final and p == 'R' and b == 'E':
            # rewrite the preceding E spelling to è + re  (…ère)
            pp, st, en = spans[-1]
            out = out[:st] + 'è'; spans[-1] = (pp, st, st + 1); g = 're'
        if final and p == 'l' and rng.random() < 0.4: g = g + 'e'
        spans.append((p, len(out), len(out) + len(g)))
        out += g
    return out, spans

def respell_check(text):
    bad = re.search(r'(ent$)|(^h)|([aeiouéèy]s[aeiouéèy])', text)  # risky readings
    return not bad

def is_real(word):
    w = word.lower().replace("'", '')
    return max(zipf_frequency(w, 'fr'), zipf_frequency(w, 'en'), zipf_frequency(w, 'es'), zipf_frequency(w, 'it')) > 0.9

# ---------------- lexicon ----------------
SUFFIXES = [['O~'], ['E', 'R'], ['y'], ['A~', 's'], ['i', 'Z'], ['o'], ['E~'], ['a', 'l']]  # recurring endings
PREFIXES = [['R', '@'], ['d', 'e'], ['a']]

def build(seed=7, n_roots=700, n_func=26):
    rng = random.Random(seed)
    lex, seen = [], set()
    def add(ph, kind):
        for _ in range(4):
            txt, sp = spell(list(ph), rng)
            if txt in seen or is_real(txt) or not respell_check(txt) or len(txt) < 2: continue
            seen.add(txt); lex.append(dict(text=txt, ph=[s[0] for s in sp], spans=sp, kind=kind)); return True
        return False
    # function words: 1 syllable, simple, very frequent
    # function words: clean CV / V shapes, the language's own touch = k/z/v onsets allowed, no silent letters
    FC = {'k': 'k', 'z': 'z', 'v': 'v', 'l': 'l', 'd': 'd', 't': 't', 'm': 'm', 'n': 'n', 'Z': 'j', 'R': 'r', 's': 's', 'p': 'p', 'b': 'b', 'f': 'f'}
    FV = {'a': 'a', 'i': 'i', 'o': 'o', 'u': 'ou', 'y': 'u', 'e': 'é', 'E': 'è', 'A~': 'an', 'O~': 'on', '2': 'eu'}
    # block what a French ear would hear as a common function word (sound, not spelling)
    BLOCK = {'la', 'l@', 'le', 'de', 'dy', 'si', 'sa', 's@', 'se', 'sE', 'ma', 'me', 'mE', 'ta', 'te', 'tu', 'ty', 'Z@', 'O~', 'A~', 'a', 'o', 'e',
             'ni', 'n@', 'ne', 'ki', 'k@', 'nu', 'vu', 'vo', 'pa', 'sO~', 'mO~', 'tO~', 'sA~', 'dA~', 'kA~', 'nO~', 'lO~', 'dO~', 'vA~', 'tA~',
             'ky', 'kE', 'mi', 'li', 'di', 'lE', 'la', 'Za', 'mo', 'lo', 'do', 'y', 'i', 'sy', 'vy', 'ry', 'le', 'ru', 'ri', 'Ri', 'Ru', 'Ry',
             'Ra', 'Re', 'RE', 'Ro', 'RA~', 'RO~', 'du', 'tE', 'sO', 'so', 'su', 'mu', 'lu', 'ly', 'ze', 'zE'}
    fun_real = lambda t: zipf_frequency(t, 'fr') > 3.5 or zipf_frequency(t, 'en') > 5.0
    cands = []
    for c, cw in [('k', 6), ('z', 5), ('v', 5), ('l', 7), ('d', 6), ('t', 5), ('m', 5), ('n', 4), ('Z', 4), ('R', 3), ('s', 3), ('p', 3), ('b', 2), ('f', 2)]:
        for v, vw in [('a', 9), ('i', 7), ('o', 6), ('e', 6), ('u', 4), ('y', 4), ('E', 3), ('A~', 3), ('O~', 3), ('2', 2)]:
            txt = FC[c] + FV[v]
            if c == 'k' and v in ('e', 'E', 'i', 'y'): pass  # 'ké','ki' fine with k
            if (c + v) in BLOCK or (c == 'R'): continue
            if not fun_real(txt): cands.append((cw * vw * rng.random(), [c, v], txt))
    for c in ('k', 'z', 'l', 'd', 'v', 'm'):  # C + ia / io glide forms
        for v, vt in (('a', 'ia'), ('o', 'io')):
            txt = FC[c] + vt
            if not fun_real(txt): cands.append((15 * rng.random(), [c, 'j', v], txt))
    for v in ('a', 'o', 'i', 'y', 'e'):
        txt = FV[v]
        if v in BLOCK: continue
        if not fun_real(txt): cands.append((20 * rng.random(), [v], txt))
    cands.sort(reverse=True)
    picked, per_v, per_c, ce = 0, {}, {}, set()
    for _, ph, txt in cands:
        if picked >= n_func: break
        v, c = ph[-1], (ph[0] if len(ph) == 2 else '')
        vk = 'e' if v in ('e', 'E') else v
        if txt in seen or per_v.get(vk, 0) >= (2 if v in ('2', 'A~', 'O~') else 7) or per_c.get(c, 0) >= 4 or (c, vk) in ce: continue
        per_v[vk] = per_v.get(vk, 0) + 1; per_c[c] = per_c.get(c, 0) + 1; ce.add((c, vk)); picked += 1
        seen.add(txt)
        if len(ph) == 3: sp = [(ph[0], 0, len(txt) - 2), ('j', len(txt) - 2, len(txt) - 1), (ph[2], len(txt) - 1, len(txt))]
        else:
            c0 = len(txt) - len(FV[ph[-1]])
            sp = ([(ph[0], 0, c0)] if len(ph) == 2 else []) + [(ph[-1], c0, len(txt))]
        lex.append(dict(text=txt, ph=ph, spans=sp, kind='func'))
    fw = sorted([w for w in lex if w['kind'] == 'func'], key=lambda w: (len(w['ph']), len(w['text'])))
    lex = fw + [w for w in lex if w['kind'] != 'func']
    # elision clitics (C + schwa): 'X' before a vowel
    for c in ['v', 'z', 'k']:
        txt = {'v': 've', 'z': 'ze', 'k': 'que'}[c]
        if not is_real(txt) and txt not in seen:
            seen.add(txt); lex.append(dict(text=txt, ph=[c, '@'], spans=[(c, 0, len(txt) - 1), ('@', len(txt) - 1, len(txt))], kind='clitic'))
    while sum(1 for w in lex if w['kind'] == 'root') < n_roots:
        ns = rng.choices([1, 2, 3], [25, 55, 20])[0]
        ph = root(rng, ns)
        if not ph: continue
        r = rng.random()
        if r < 0.28 and ns <= 2:
            suf = list(rng.choice(SUFFIXES))
            if ph[-1] == suf[0]: continue
            if ph[-1] in V_W and suf[0] in V_W: ph = ph + [rng.choice(['l', 'R', 'v', 's', 'd'])]
            if ph[-1] in NASAL: ph = ph + ['t']
            ph = ph + suf
        elif r < 0.36:
            pre = list(rng.choice(PREFIXES))
            if pre[-1] == '@' and ph[0] in V_W: pre = pre[:-1]
            elif pre[-1] in V_W and ph[0] in V_W: ph = ['v'] + ph
            if pre[-1] == ph[0] or (pre[-1] not in V_W and ph[0] not in V_W and (pre[-1], ph[0]) not in ONSET2): continue
            ph = pre + ph
        add(ph, 'root')
    return lex

# ---------------- relexification of an English script ----------------
FUNC_MAP = [  # groups of English function words -> one invented function word each (in order of frequency)
    ['the', 'a', 'an'], ['of', 'from'], ['and'], ['to', 'into', 'toward', 'towards'], ['in', 'on', 'at'], ['is', 'are', 'am', 'be', 'was', 'were'],
    ['i', 'me'], ['you'], ['he', 'him', 'she', 'her', 'it'], ['we', 'us'], ['they', 'them'], ['not', "n't", 'no'], ['that', 'this', 'those', 'these'],
    ['my', 'mine'], ['your', 'yours'], ['his', 'its', 'their', 'our'], ['what', 'which'], ['where', 'there', 'here'], ['with'], ['for'],
    ['will', 'shall', 'would', 'do', 'does', 'did', 'have', 'has', 'had'], ['then', 'so'],
]

def word_hash(w):
    return int(hashlib.md5(w.encode()).hexdigest()[:8], 16)

def syl_count(w):
    return max(1, len(re.findall(r'[aeiouy]+', w.lower())) - (1 if w.lower().endswith('e') and len(w) > 3 else 0))

class Relex:
    def __init__(self, lex, seed=7):
        self.lex = lex
        self.func = [w for w in lex if w['kind'] == 'func']
        self.clitic = [w for w in lex if w['kind'] == 'clitic']
        self.roots = [w for w in lex if w['kind'] == 'root']
        self.fmap = {}
        for i, grp in enumerate(FUNC_MAP):
            for e in grp: self.fmap[e] = self.func[i % len(self.func)]
        self.cache, self.used = {}, set()
        self.rng = random.Random(seed)
    def content(self, en):
        k = en.lower()
        if k in self.cache: return self.cache[k]
        target = min(3, syl_count(k))
        pool = [w for w in self.roots if abs(sum(1 for p in w['ph'] if p in V_W) - target) <= 0 and w['text'] not in self.used]
        if not pool: pool = [w for w in self.roots if w['text'] not in self.used]
        w = pool[word_hash(k) % len(pool)]
        self.used.add(w['text']); self.cache[k] = w; return w
    def name(self, en):
        w = self.content(en + '#name'); return dict(w, text=w['text'][0].upper() + w['text'][1:])
    def sentence(self, english):
        """Map an English line -> (text, words) keeping punctuation, CAPS emphasis and [tags]."""
        toks = re.findall(r"\[[^\]]+\]|[A-Za-z']+|\.\.\.|[.,!?;:]", english)
        out, words, first = [], [], True
        for t in toks:
            if t.startswith('['): out.append(t); continue
            if re.fullmatch(r"\.\.\.|[.,!?;:]", t):
                out.append(t); first = t in '.!?...' or first
                continue
            caps = t.isupper() and len(t) > 1
            low = t.lower().replace("'s", '')
            if low in self.fmap: w = self.fmap[low]
            elif t[0].isupper() and not first: w = self.name(low)
            else: w = self.content(low)
            txt = w['text']
            if caps: txt = txt.upper()
            elif first: txt = txt[0].upper() + txt[1:]
            first = False
            out.append(txt); words.append(dict(en=t, text=txt, ph=w['ph'], spans=w['spans']))
        # join: no space before punctuation; elision clitic' + vowel-initial word
        s = ''
        for tok in out:
            if re.fullmatch(r"\.\.\.|[.,!?;:]", tok): s = s.rstrip() + tok + ' '
            else: s += tok + ' '
        return re.sub(r'\s+', ' ', s).strip(), words

if __name__ == '__main__':
    lex = build()
    func = [w['text'] for w in lex if w['kind'] in ('func', 'clitic')]
    roots = [w['text'] for w in lex if w['kind'] == 'root']
    print('function words:', func)
    print('roots sample:', roots[:60])
