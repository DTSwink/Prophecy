"""Invented language v3 = lang2 grammar + two accent/prosody fixes (Nov 4, after the English-vs-gibberish A/B).

1) French-looking spelling (same sounds). ElevenLabs guesses the accent from the spelling, and v2 spelled some words
   like Spanish/Italian (final -a/-o/-u, k-, 'mio', 'lia', plural 'cécassi'), which pulled some words towards a rolled
   Spanish r. v3 spells every word ending the French way:
     final a -> at/as | o -> eau/ot/aut | y(u) -> ue/ut | i -> i/is/it | e+R / E+R -> ère | a+R -> are/ard | O+R -> ore/ort
     plural nouns: silent French -s instead of the audible -i | -ly -> -mant | function words: kon->quon, ké->quez (elides qu'), kou->cou,
     jou->joux, ju->jus, mio->miot, lia->liat, nèk->nèque, pliza->plizat, kazé->cazé
2) Syllable parity: a root gets as many syllables as its English word (CMU dict, 1..3), so the gibberish line has
   about the same rhythm as the English it carries. Existing roots with the right length are kept (language memory).
3) translate_aligned(): also returns, for every gibberish word, the English word it comes from (for prosody transfer).
"""
import re, json, random, hashlib, gzip
import lang, lang2
from lang import V_W, NASAL
from lang2 import Lang2, LEM, wn_pos, INTERJ, CONTR, BANGS, NEG2, num_words
from wordfreq import zipf_frequency

_spell_v2 = lang.spell

def _h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

def spell3(ph, rng):
    ph = list(ph)
    txt, sp = _spell_v2(list(ph), rng)
    if not sp: return txt, sp
    key = ''.join(p for p in ph if p)
    last = [p for p in ph if p]
    p1 = last[-1]; p0 = last[-2] if len(last) > 1 else None
    ps, st, en = sp[-1]
    tail = txt[st:]
    new = None
    if p1 == 'a' and tail == 'a': new = 'at' if _h(key) % 3 else 'as'
    elif p1 == 'o' and tail in ('o', 'ot', 'eau'): new = ['eau', 'ot', 'aut'][_h(key) % 3]
    elif p1 == 'y' and tail == 'u' and len(last) > 2: new = 'ue' if _h(key) % 2 else 'ut'
    elif p1 == 'i' and tail == 'i' and len(last) > 3: new = ['i', 'is', 'it', 'i'][_h(key) % 4]
    elif p1 == 'R' and p0 in ('a', 'O', 'o', 'e', 'y') and len(sp) > 1 and txt[sp[-2][1]:sp[-2][2]] in ('a', 'o', 'au', 'é', 'u', 'è', 'e'):
        # rewrite the vowel before the final R too
        vs, vst, ven = sp[-2]
        ending = {'a': ['are', 'ard'], 'O': ['ore', 'ort'], 'o': ['ore', 'ort'], 'e': ['ère', 'ère'], 'y': ['ure', 'ure']}[p0][_h(key) % 2]
        vg, rg = ending[0], ending[1:]
        txt = txt[:vst] + vg + rg
        sp = sp[:-2] + [(vs, vst, vst + len(vg)), ('R', vst + len(vg), len(txt))]
        return txt, sp
    if new is not None:
        txt = txt[:st] + new
        sp = sp[:-1] + [(ps, st, len(txt))]
    return txt, sp

# lang2 imported `spell` by name; patch both modules so every root/name/form uses v3 spelling
lang.spell = spell3
lang2.spell = spell3

FUNC_RESPELL = {'kon': 'quon', 'ké': 'quez', 'kou': 'cou', 'jou': 'joux', 'ju': 'jus', 'mio': 'miot', 'lia': 'liat'}
FIXED3 = {'yes': 'vèl', 'yeah': 'vèl', 'yep': 'vèl', 'yup': 'vèl', 'no': 'nèque', 'nope': 'nèque', 'okay': 'tavé', 'ok': 'tavé',
          'alright': 'tavé', 'please': 'plizat', 'thanks': 'mérsil', 'thank': 'mérsil', 'sorry': 'dézou', 'hi': 'bénou',
          'hello': 'bénou', 'bye': 'cazé', 'goodbye': 'cazé'}
ELIDE3 = {'dè': "d'", 'quez': "qu'", 'jé': "j'", 'vé': "v'"}

_CMU = None
def en_syllables(word):
    global _CMU
    if _CMU is None:
        from nltk.corpus import cmudict
        _CMU = cmudict.dict()
    w = word.lower()
    if w in _CMU: return min(sum(1 for p in pr if p[-1].isdigit()) for pr in _CMU[w])
    return max(1, len(re.findall(r'[aeiouy]+', w)) - (1 if w.endswith('e') and len(w) > 3 else 0))

def ph_syllables(ph):
    return sum(1 for p in ph if p in V_W)


class Lang3(Lang2):
    def __init__(self, seed=7, lexicon=None):
        super().__init__(seed, lexicon)
        for w in self.func:
            if w['text'] in FUNC_RESPELL:
                old = w['text']; new = FUNC_RESPELL[old]
                w['text'] = new
                # spans: consonant part = everything before the vowel letters, vowel part = rest (sound spans unchanged)
                ph = w['ph']
                vstart = {'quon': 2, 'quez': 2, 'cou': 1, 'joux': 1, 'jus': 1, 'miot': 1, 'liat': 1}[new]
                if len(ph) == 3:   # C j V
                    w['spans'] = [(ph[0], 0, 1), ('j', 1, 2), (ph[2], 2, len(new))]
                else:
                    w['spans'] = [(ph[0], 0, vstart), (ph[1], vstart, len(new))]
                self.forms[new] = w['spans']
        lang2.FIXED.clear(); lang2.FIXED.update(FIXED3)
        lang2.ELIDE.clear(); lang2.ELIDE.update(ELIDE3)
        self.taken |= {w['text'] for w in self.func} | set(FIXED3.values())
        self.kept, self.remade = 0, 0
        self._parity_checked = set()

    def _new_root(self, key, nsyl, name=False):
        # v3: 1-syllable roots run out fast with the strict real-word filter, which made short English words long.
        # For 1 syllable only common real words are blocked (fr zipf>2.0, en>3.0), and we try 4x longer before growing.
        rng = random.Random(int(hashlib.md5(key.encode()).hexdigest()[:12], 16))
        per = 600 if nsyl == 1 else 150
        for k in range(per * 3):
            n = min(4, nsyl + k // per)
            ph = lang.root(rng, n)
            if not ph or (name and ph[-1] in NASAL): continue
            txt, sp = lang.spell(list(ph), random.Random(1))
            if txt in self.taken or len(txt) < 2 or not lang.respell_check(txt): continue
            if n == 1:
                w = txt.replace("'", '')
                if zipf_frequency(w, 'fr') > 2.0 or zipf_frequency(w, 'en') > 3.0 or max(zipf_frequency(w, 'es'), zipf_frequency(w, 'it')) > 3.5: continue
            elif lang.is_real(txt): continue
            self.taken.add(txt); return ph
        raise RuntimeError('no root for ' + key)

    def root_for(self, lemma):
        if lemma.startswith('num:'): target = en_syllables(lemma[4:])
        else: target = en_syllables(lemma)
        target = max(1, min(3, target))
        if lemma in self.roots and lemma not in self._parity_checked:
            self._parity_checked.add(lemma)
            if ph_syllables(self.roots[lemma]) == target: self.kept += 1
            else:
                del self.roots[lemma]; self.remade += 1
        if lemma not in self.roots:
            self._parity_checked.add(lemma)
            self.roots[lemma] = self._new_root('r3:' + lemma, target)
        return list(self.roots[lemma])

    def inflect(self, ph, tag):
        return super().inflect(ph, tag)

    def form(self, ph, cap=False, plural=False):
        txt, sp = lang.spell(list(ph), random.Random(1))
        if plural and not txt.endswith(('s', 'x', 'z')):
            # French plural: silent -s (-x after eau/ou/eu), the sound does not change
            txt = txt + ('x' if txt.endswith(('eau', 'au', 'eu')) else 's'); sp = sp[:-1] + [(sp[-1][0], sp[-1][1], len(txt))]
        self.forms.setdefault(txt, sp)
        return txt[0].upper() + txt[1:] if cap else txt

    # ---- translation with word alignment ----
    def translate_aligned(self, english):
        """-> (text, words): words = [{'g': gibberish word as written (punct attached), 'src': english word index or None}]
        English word index = index into english_words(english) (whitespace words of the line without [tags])."""
        tags = re.findall(r'\[[^\]]+\]', english)
        body = re.sub(r'\[[^\]]+\]', ' ', english)
        ewords = body.split()
        toks = []   # (token, english word index)
        for wi, ew in enumerate(ewords):
            x = ew.replace('—', ', ').replace('--', ', ')
            for a, b in CONTR: x = re.sub(a, b, x, flags=re.I)
            for t in re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*|\d+|\.\.\.|[.,!?;:]", x): toks.append((t, wi))
        if not toks: return ' '.join(tags + ['...']), []
        words = [t for t, _ in toks if re.match(r'[A-Za-z\d]', t)]
        tagged = lang2.pos_tag(words) if words else []
        ti = iter(tagged)
        seq = []
        for t, wi in toks:
            if re.match(r'[A-Za-z\d]', t): w, p = next(ti); seq.append([w, p, wi])
            else: seq.append([t, 'PUNCT', wi])
        out = []
        for i, (w, p, wi) in enumerate(seq):
            lw = w.lower(); nxt = seq[i + 1] if i + 1 < len(seq) else ['', '', None]
            if lw in ('do', 'does', 'did') and (nxt[1] in ('PRP', 'NNP', 'NN', 'DT') or nxt[0].lower() in ('not', 'you', 'i', 'we', 'they')) and p != 'VB':
                continue
            out.append([w, p, wi])
        seq = out
        i = 0
        while i < len(seq) - 1:
            if seq[i][1] == 'JJ' and seq[i + 1][1] in ('NN', 'NNS') and seq[i][0].lower() not in BANGS:
                seq[i], seq[i + 1] = seq[i + 1], seq[i]; i += 2
            else: i += 1
        res, first, neg_pending, neg_src = [], True, False, None
        FIX = lang2.FIXED
        for (w, p, wi) in seq:
            if p == 'PUNCT':
                if neg_pending: res.append((NEG2, neg_src)); neg_pending = False
                res.append((w, None))
                if w in '.!?': first = True
                continue
            lw = w.lower(); caps = w.isupper() and len(w) > 2
            if lw in ('not', 'never'):
                res.append((self.fmap['not']['text'], wi)); neg_pending = True; neg_src = wi
                if lw == 'never': res.append((self.form(self.root_for('ever')), wi))
                first = False; continue
            if re.fullmatch(r'\d+', w):
                for nw in num_words(w): res.append((self.form(self.root_for('num:' + nw)), wi))
                first = False; continue
            if lw in INTERJ: tok = INTERJ[lw]
            elif lw in FIX: tok = FIX[lw]
            elif lw in self.fmap: tok = self.fmap[lw]['text']
            elif (p in ('NNP', 'NNPS') and not first and w[0].isupper()) or (w[0].isupper() and lw in self.known_names
                                                                              and (not first or zipf_frequency(lw, 'en') < 4.0)):
                tok = self.form(self.name_for(w), cap=True)
            else:
                lemma = LEM.lemmatize(lw, wn_pos(p)) if p[0] in 'NVJR' else lw
                if p == 'RB' and lw.endswith('ly') and len(lw) > 4:
                    base = LEM.lemmatize(lw[:-2], 'a')
                    tok = self.form(self.root_for(base) + ['m', 'A~'])
                    if tok.endswith('man'): tok = tok[:-3] + 'mant'
                    elif tok.endswith('mant') is False and tok.endswith('mand'): pass
                else:
                    pl = p in ('NNS', 'NNPS')
                    tok = self.form(self.inflect(self.root_for(lemma), 'NN' if pl else p), plural=pl)
            if caps: tok = tok.upper()
            elif first: tok = tok[0].upper() + tok[1:]
            res.append((tok, wi)); first = False
            if neg_pending and p.startswith('V'): res.append((NEG2, neg_src)); neg_pending = False
        if neg_pending: res.append((NEG2, neg_src))
        # join (elision merges a clitic into the next word; punctuation attaches to the previous word)
        gw = []   # [text, src]
        interj = set(INTERJ.values()) | {'y'}
        pending = None
        for i, (tk, src) in enumerate(res):
            if re.fullmatch(r"\.\.\.|[.,!?;:]", tk):
                if gw: gw[-1][0] += tk
                else: gw.append([tk, None])
                continue
            nxt = res[i + 1][0] if i + 1 < len(res) else ''
            low = tk.lower()
            if low in lang2.ELIDE and nxt and nxt[0].lower() in 'aeiouéèàâêîôûy' and nxt.lower() not in interj:
                e = lang2.ELIDE[low]; pending = (e[0].upper() + e[1:] if tk[0].isupper() else e); continue
            if pending: tk = pending + tk; pending = None
            gw.append([tk, src])
        if gw and gw[0][0][0].islower(): gw[0][0] = gw[0][0][0].upper() + gw[0][0][1:]
        text = ' '.join(g for g, _ in gw)
        text = (' '.join(tags) + ' ' + text).strip() if tags else text
        return text, [dict(g=g, src=s) for g, s in gw]

    def translate(self, english):
        return self.translate_aligned(english)[0]


def load(lex_path='/home/claude/corpus/lexicon_v2.json.gz', seed=7):
    lex = json.load(gzip.open(lex_path, 'rt', encoding='utf8')) if lex_path.endswith('.gz') else json.load(open(lex_path, encoding='utf8'))
    L = Lang3(seed, lex)
    for n in lex.get('names', {}): L.known_names.add(n)
    return L
