"""Make an el_accent experiment for a batch at one rung of the French-accent ladder (no API calls).

  python Tools/Speech/accent_ladder.py Tools/Speech/batches/<batch>.json --level 1 [--lines 0,2,4] [--seed 4242] [--speakers S1]
  -> Tools/Speech/accent/<batch>_L<level>_s<seed>.json, then run el_accent.py on it and score the takes (Whisper LID).

The ladder (Nov 6 2026 experiments, 26 Seller lines + Customer checks, eleven_v4, Marcel_FR / Sarah_FR):
  every rung uses TAG (a *southern* French accent tag; "[French accent]", "[strong/thick French accent]" do far less)
  L0  classical Occitan spelling              ~50% of Seller lines read as French (>= 0.9)
  L1  French-looking spelling, final -a -> -o  ~80%   (occ_frspell.frspell(text))
  L2  French-looking spelling, mute -e         100% (11/11) but closest to plain French (frspell(text, 'e'))
Recommended: generate everything at L1, score, regenerate only the failures at L2 (about 1.2x the credits of one pass).
Gate: Whisper-small LID French >= 0.90 on the whole line (accent_eval.py, run by Claude in the cloud).
Things that did NOT help (don't retry): a French primer sentence before the line (made it worse), previous_text,
language_code 'fr' (ignored by v4), stability/similarity 0.8/1.0, several lines in one request, repeating the tag."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from occ_frspell import frspell

TAG = '[thick French accent from the south of France]'

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('batch'); ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--lines', default=''); ap.add_argument('--seed', type=int, default=4242); ap.add_argument('--speakers', default='')
    a = ap.parse_args()
    B = json.loads(Path(a.batch).read_text(encoding='utf8'))
    keep = {int(x) for x in a.lines.split(',') if x}; spk = set(filter(None, a.speakers.split(',')))
    R = []
    for i, l in enumerate(B['lines']):
        if (keep and i not in keep) or (spk and l['speaker'] not in spk): continue
        emo = ' '.join(t for t in l.get('tags', '').replace('[French accent]', '').split() if t).strip()
        t = l['text'] if a.level == 0 else frspell(l['text'], 'o' if a.level == 1 else 'e')
        R.append(dict(id=f"{i:02d}_{l['speaker']}_L{a.level}_s{a.seed}", speaker=l['speaker'], line=f'{i:02d}', level=a.level,
                      classical=l['text'], english=l.get('english', ''), text=' '.join(x for x in (TAG, emo, t) if x)))
    name = f"{Path(a.batch).stem}_L{a.level}_s{a.seed}"
    E = dict(name=name, voices=B['voices'], defaults=dict(model_id='eleven_v4', seed=a.seed), requests=R)
    out = Path(__file__).resolve().parent / 'accent' / (name + '.json'); out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(E, ensure_ascii=False, indent=1), encoding='utf8')
    print(out, len(R), 'requests', sum(len(r['text']) for r in R), 'characters')
    for r in R: print(' ', r['id'], r['text'])

if __name__ == '__main__':
    main()
