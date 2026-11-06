"""Grammar layer for the invented language (v2). Builds on lang.py sounds/spelling/function words.

English is only a meaning scaffold. Translation rules (make it behave like a language, not a cipher):
- Lemma-consistent roots: run/ran/running share one root; roots are longer for rarer English words (Zipf).
- Inflection by part of speech (NLTK tagger + WordNet lemmatizer):
    plural nouns -i (after a vowel -zi) | past -ette (-vette) | -ing -an (-dan) | -ly -man | comparative/superlative -on
    3rd person present: unchanged (silent, as in French).
- French-like order: adjective after the noun, except beauty/age/number/goodness/size adjectives (French BANGS).
- Negation is a circumfix like French ne...pas: 'zou' before the verb, 'teu' after it.
- English do-support is dropped (questions/negations), contractions are expanded.
- Elision: dè/ké/jé/vé + vowel-initial word -> d'/k'/j'/v' (one phonological word).
- Names (proper nouns, speaker names) map to consistent capitalised invented names. Numbers -> invented numerals.
- Interjections: oh/ah/hm/huh kept (universal), um/uh -> euh, wow -> ouah, plus invented yes/no/okay/please/thanks/sorry/hi/bye.
Every produced word form is recorded with its sound spans (forms lexicon) for viseme baking.
"""
import re, json, random, hashlib
from nltk import pos_tag
from nltk.stem import WordNetLemmatizer
from wordfreq import zipf_frequency
import lang
from lang import build, spell, syllable, root, is_real, respell_check, V_W, NASAL, FUNC_MAP

LEM = WordNetLemmatizer()
BANGS = set('good bad great little small big large old young new long short beautiful pretty ugly first last other same few many whole only own next'.split())
CONTR = [(r"\bwon't\b", 'will not'), (r"\bcan't\b", 'can not'), (r"\bcannot\b", 'can not'), (r"\bshan't\b", 'shall not'), (r"\bain't\b", 'is not'),
         (r"n't\b", ' not'), (r"'re\b", ' are'), (r"'m\b", ' am'), (r"'ve\b", ' have'), (r"'ll\b", ' will'), (r"'d\b", ' would'),
         (r"\b(it|that|what|there|here|he|she|who|where|how|this|everything|nothing|something|everyone|let)'s\b", r'\1 is'),
         (r"'s\b", ''), (r"s'\b", 's'), (r"\bgonna\b", 'going to'), (r"\bwanna\b", 'want to'), (r"\bgotta\b", 'got to'),
         (r"\bc'mon\b", 'come on'), (r"\by'know\b", 'you know'), (r"\bwhaddya\b", 'what do you'), (r"\b'cause\b", 'because')]
INTERJ = {'oh': 'oh', 'ah': 'ah', 'hm': 'hm', 'hmm': 'hmm', 'mm': 'mm', 'huh': 'heu', 'um': 'euh', 'uh': 'euh', 'er': 'euh', 'erm': 'euh',
          'wow': 'ouah', 'whoa': 'ouah', 'ow': 'aïe', 'ouch': 'aïe', 'oops': 'oups', 'haha': 'ha ha', 'ha': 'ha', 'hey': 'hé'}
FIXED = {'yes': 'vèl', 'yeah': 'vèl', 'yep': 'vèl', 'yup': 'vèl', 'no': 'nèk', 'nope': 'nèk', 'okay': 'tavé', 'ok': 'tavé', 'alright': 'tavé',
         'please': 'pliza', 'thanks': 'mérsil', 'thank': 'mérsil', 'sorry': 'dézou', 'hi': 'bénou', 'hello': 'bénou', 'bye': 'kazé', 'goodbye': 'kazé'}
NEG2 = 'teu'
ELIDE = {'dè': "d'", 'ké': "k'", 'jé': "j'", 'vé': "v'"}
SUFFIX = {'NNS': (['i'], ['z', 'i']), 'NNPS': (['i'], ['z', 'i']), 'VBD': (['E', 't'], ['v', 'E', 't']), 'VBN': (['E', 't'], ['v', 'E', 't']),
          'VBG': (['A~'], ['d', 'A~']), 'JJR': (['O~'], ['l', 'O~']), 'JJS': (['O~'], ['l', 'O~']), 'RBR': (['O~'], ['l', 'O~']),
          'RBS': (['O~'], ['l', 'O~'])}
NUM = {'0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four', '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'}

def num_words(n):
    n = int(n)
    if n < 10: return [NUM[str(n)]]
    small = 'ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
    tens = 'x x twenty thirty forty fifty sixty seventy eighty ninety'.split()
    if n < 20: return [small[n - 10]]
    if n < 100: return [tens[n // 10]] + ([NUM[str(n % 10)]] if n % 10 else [])
    if n < 1000: return [NUM[str(n // 100)], 'hundred'] + (num_words(n % 100) if n % 100 else [])
    return num_words(n // 1000) + ['thousand'] + (num_words(n % 1000) if n % 1000 else [])

def wn_pos(tag):
    return {'N': 'n', 'V': 'v', 'J': 'a', 'R': 'r'}.get(tag[0], 'n')

class Lang2:
    def __init__(self, seed=7, lexicon=None):
        self.lex = build(seed)
        self.func = [w for w in self.lex if w['kind'] == 'func']
        self.fmap = {}
        for i, grp in enumerate(FUNC_MAP):
            for e in grp: self.fmap[e] = self.func[i % len(self.func)]
        self.taken = {w['text'] for w in self.lex if w['kind'] == 'func'} | set(FIXED.values()) | {NEG2}
        self.roots = dict(lexicon['roots']) if lexicon else {}     # english lemma -> phoneme list
        self.names = dict(lexicon['names']) if lexicon else {}
        for ph in list(self.roots.values()) + list(self.names.values()):
            self.taken.add(spell(list(ph), random.Random(1))[0])
        self.forms = {}   # spelled form -> [(phoneme, start, end)]
        for w in self.func: self.forms[w['text']] = w['spans']
        self.known_names = set()

    # ---- roots ----
    def _new_root(self, key, nsyl, name=False):
        rng = random.Random(int(hashlib.md5(key.encode()).hexdigest()[:12], 16))
        for k in range(600):
            ph = root(rng, min(4, nsyl + k // 150))   # short slots run out -> go one syllable longer
            if name and ph[-1] in NASAL: continue
            txt, sp = spell(list(ph), random.Random(1))
            if txt in self.taken or is_real(txt) or not respell_check(txt) or len(txt) < 2: continue
            self.taken.add(txt); return ph
        raise RuntimeError('no root for ' + key)

    def root_for(self, lemma):
        if lemma not in self.roots:
            z = zipf_frequency(lemma, 'en')
            rng = random.Random(lemma)
            nsyl = 1 if z >= 5.6 else (rng.choice([1, 2]) if z >= 4.6 else (2 if z >= 3.6 else rng.choice([2, 2, 3])))
            self.roots[lemma] = self._new_root('r:' + lemma, nsyl)
        return list(self.roots[lemma])

    def name_for(self, en):
        k = en.lower()
        if k not in self.names: self.names[k] = self._new_root('n:' + k, 2, name=True)
        return list(self.names[k])

    # ---- forms ----
    def form(self, ph, cap=False):
        txt, sp = spell(list(ph), random.Random(1))
        self.forms.setdefault(txt, sp)
        return txt[0].upper() + txt[1:] if cap else txt

    def inflect(self, ph, tag):
        suf = SUFFIX.get(tag)
        if tag in ('RB',) and False: pass
        if not suf: return ph
        after_v = ph[-1] in V_W
        s = list(suf[1] if after_v else suf[0])
        if ph[-1] in NASAL and s[0] in V_W: s = ['t'] + s
        if ph[-1] == s[0]: s = s[1:] or s
        return ph + s

    # ---- sentence ----
    def translate(self, english):
        """English line (may contain [tags]) -> invented-language text. Tags/punctuation/CAPS kept."""
        tags = re.findall(r'\[[^\]]+\]', english)
        body = re.sub(r'\[[^\]]+\]', ' ', english)
        body = body.replace('—', ', ').replace('--', ', ')
        for a, b in CONTR: body = re.sub(a, b, body, flags=re.I)
        toks = re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*|\d+|\.\.\.|[.,!?;:]", body)
        if not toks: return ' '.join(tags + ['...'])
        words = [t for t in toks if re.match(r'[A-Za-z\d]', t)]
        tagged = pos_tag([w for w in words]) if words else []
        ti = iter(tagged)
        seq = []
        for t in toks:
            if re.match(r'[A-Za-z\d]', t): w, p = next(ti); seq.append([w, p])
            else: seq.append([t, 'PUNCT'])
        # drop do-support: do/does/did followed by subject pronoun/noun or by 'not'
        out = []
        for i, (w, p) in enumerate(seq):
            lw = w.lower()
            nxt = seq[i + 1] if i + 1 < len(seq) else ['', '']
            if lw in ('do', 'does', 'did') and (nxt[1] in ('PRP', 'NNP', 'NN', 'DT') or nxt[0].lower() in ('not', 'you', 'i', 'we', 'they')) and p != 'VB':
                continue
            out.append([w, p])
        seq = out
        # adjective after noun (non-BANGS)
        i = 0
        while i < len(seq) - 1:
            if seq[i][1] == 'JJ' and seq[i + 1][1] in ('NN', 'NNS') and seq[i][0].lower() not in BANGS:
                seq[i], seq[i + 1] = seq[i + 1], seq[i]; i += 2
            else: i += 1
        res, first, neg_pending = [], True, False
        for idx, (w, p) in enumerate(seq):
            if p == 'PUNCT':
                if neg_pending: res.append(NEG2); neg_pending = False
                res.append(w)
                if w in '.!?': first = True
                continue
            lw = w.lower(); caps = w.isupper() and len(w) > 2
            if lw in ('not', 'never'):
                res.append(self.fmap['not']['text']); neg_pending = True
                if lw == 'never': res.append(self.form(self.root_for('ever')))
                first = False; continue
            if re.fullmatch(r'\d+', w):
                for nw in num_words(w): res.append(self.form(self.root_for('num:' + nw)))
                first = False; continue
            if lw in INTERJ: tok = INTERJ[lw]
            elif lw in FIXED: tok = FIXED[lw]
            elif lw in self.fmap: tok = self.fmap[lw]['text']
            elif (p in ('NNP', 'NNPS') and not first and w[0].isupper()) or (w[0].isupper() and lw in self.known_names):
                tok = self.form(self.name_for(w), cap=True)
            else:
                lemma = LEM.lemmatize(lw, wn_pos(p)) if p[0] in 'NVJR' else lw
                if p == 'RB' and lw.endswith('ly') and len(lw) > 4:
                    base = LEM.lemmatize(lw[:-2], 'a')
                    tok = self.form(self.root_for(base) + ['m', 'A~'])
                else:
                    tok = self.form(self.inflect(self.root_for(lemma), p))
            if caps: tok = tok.upper()
            elif first: tok = tok[0].upper() + tok[1:]
            res.append(tok); first = False
            if neg_pending and p.startswith('V'): res.append(NEG2); neg_pending = False
        if neg_pending: res.append(NEG2)
        # elision + joining
        s = ''
        toks2 = res
        for i, tk in enumerate(toks2):
            if re.fullmatch(r"\.\.\.|[.,!?;:]", tk): s = s.rstrip() + tk + ' '; continue
            nxt = toks2[i + 1] if i + 1 < len(toks2) else ''
            low = tk.lower()
            if low in ELIDE and nxt and nxt[0].lower() in 'aeiouéèàâêîôûy' and nxt.lower() not in set(INTERJ.values()) | {'y'}:
                e = ELIDE[low]; s += (e[0].upper() + e[1:] if tk[0].isupper() else e); continue
            s += tk + ' '
        s = re.sub(r'\s+', ' ', s).strip()
        s = re.sub(r'^([a-zàâéèêîôûç])', lambda m: m.group(1).upper(), s)
        return (' '.join(tags) + ' ' + s).strip() if tags else s

    def export(self):
        return dict(roots=self.roots, names=self.names)
