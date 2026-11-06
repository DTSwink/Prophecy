"""Occitan (Lengadocian, classical spelling) -> French-looking phonetic spelling, for TTS only.
Why: eleven_v4 picks the language from the text. Classical Occitan spelling (-as, -os, frescas, pomas) reads as
Spanish/Portuguese/Italian and the model speaks it "fluently" in that phonology, even with a French accent tag.
Written with French conventions (ou, -o, silent final consonants dropped) it is read as French with the voice's own
accent. The words and their sounds stay Occitan (roughly as a southern French speaker says them).
Rules (Nov 2026, tuned on the apples scene): o->ou (ò stays), final unstressed -a/-as->-o, lh->lh->ill, nh->gn,
final -r/-rn silent (panièr->panié, jorn->jour), ai->aï, final plural -s dropped (pomas->poumo).
Always listen-check / detector-check: this is a heuristic, not a transliteration standard."""
import re
FUNC = {'lo': 'lou', 'los': 'lous', 'las': 'li', 'dos': 'dous', 'son': 'soun', 'de': 'dé', 'e': 'é', 'es': 'ès',
        'un': 'un', 'una': 'uno', 'a': 'a', 'al': 'au', 'pas': 'pa', 'me': 'mé', 'te': 'té', 'se': 'sé', 'que': 'qué',
        'ai': 'aï', 'va': 'va', 'la': 'la', 'bonjorn': 'bonjour'}
def word(w, ending='o'):
    lw = w.lower()
    if ending == 'e' and lw in ('una', 'la', 'las'): out = {'una': 'une', 'la': 'la', 'las': 'les'}[lw]
    elif lw in FUNC: out = FUNC[lw]
    else:
        out = lw.replace('lh', 'ill').replace('nh', 'gn')
        out = re.sub(r"o(?![uù])", "ou", out).replace('ó', 'ou')                       # o = [u]; ò stays [ɔ]
        if ending == 'e':   # French mute-e look (level 2: strongest French reading, closest to French)
            out = re.sub(r"c(as?)$", r"qu\1", out); out = re.sub(r"g(as?)$", r"gu\1", out)
            out = re.sub(r"as$", "es", out); out = re.sub(r"a$", "e", out)
        else:
            out = re.sub(r"as$", "o", out); out = re.sub(r"a$", "o", out)             # unstressed final -a(s) = [ɔ]
        out = re.sub(r"ous$", "ou", out); out = re.sub(r"òus$", "òu", out)             # sòus -> sòu
        out = re.sub(r"ourn$", "our", out)                                               # jorn -> jour
        out = re.sub(r"([èé])r$", "é", out)                                              # panièr -> panié
        out = re.sub(r"g$", "ch", out)                                                   # mièg -> mièch
        if lw.endswith('es'): out = re.sub(r"(?<=[^aeiouèéòàí])es$", "é", out)          # pèrdes -> pèrdé
        if out.endswith('ai'): out = out[:-2] + 'aï'
    if w[:1].isupper(): out = out[:1].upper() + out[1:]
    return out
def frspell(text, ending='o'):
    """keeps punctuation and apostrophes (l'alba -> l'albo). ending 'o' (level 1) or 'e' (level 2, mute-e)"""
    def rep(m):
        t = m.group(0)
        if "'" in t: a, b = t.split("'", 1); return a + "'" + word(b, ending)
        return word(t, ending)
    return re.sub(r"[A-Za-zÀ-ÿ']+", rep, text)
if __name__ == '__main__':
    import sys, json
    for t in sys.argv[1:]: print(frspell(t))
