"""Build the accent-fixed apples scene from the approved batch + the chosen accent-experiment takes (no API calls).
  python Tools/Speech/accent_assemble.py
-> Saved/Speech/ab_apples_occ_fv_accentfix/
     v4/NN_Sx.mp3 + .json   the scene to use (same layout as el_generate batches; replaced lines carry the classical
                            Occitan 'text', the 'spoken' text actually sent, the accent method and the detector score)
     orig/                  the approved takes, for A/B listening
     manifest.json, index.html (play each line / the whole scene per column)
The approved batch folder is not modified."""
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from el_generate import ROOT, PAGE

SRC = ROOT / 'Saved/Speech/ab_apples_occ_fv_tag'
ACC = ROOT / 'Saved/Speech/accent'
OUT = ROOT / 'Saved/Speech/ab_apples_occ_fv_accentfix'
TAG = '[thick French accent from the south of France]'
# French-language probability (Whisper-small LID, whole line / worst 2.5 s window), cloud scoring Nov 6
ORIG_FR = {0: (0.01, 0.01), 1: (0.96, 0.91), 2: (0.11, 0.01), 3: (0.95, 0.93), 4: (0.12, 0.03), 5: (0.99, 0.98), 6: (0.97, 0.80), 7: (1.00, 0.99)}
PICK = {  # line -> (experiment take, method, emotion tag, LID fr, worst window)
    0: ('r6/00_Afs_s9', 'level 1: southern accent tag + French-looking spelling (occ_frspell, -o)', '[warmly]', 0.94, 0.89),
    2: ('r2/02_A_s77', 'level 0: southern accent tag, classical spelling', '[chuckles]', 0.99, 0.90),
    4: ('r2/04_A_s77', 'level 0: southern accent tag, classical spelling', '', 0.96, 0.81),
}

def main():
    mf = SRC / 'manifest.json'
    if not mf.exists(): mf = Path(__file__).resolve().parent / 'batches/ab_apples_occ_fv_tag.json'
    base = json.loads(mf.read_text(encoding='utf8'))
    for d in ('v4', 'orig'): (OUT / d).mkdir(parents=True, exist_ok=True)
    fixed, orig = [], []
    for i, l in enumerate(base['lines']):
        stem = f"{i:02d}_{l['speaker']}"
        rec = json.loads((SRC / 'v4' / (stem + '.json')).read_text(encoding='utf8'))
        for ext in ('.mp3', '.json'): shutil.copy2(SRC / 'v4' / (stem + ext), OUT / 'orig' / (stem + ext))
        orig.append(dict(rec, audio=f'orig/{stem}.mp3', lid_fr=ORIG_FR[i][0], lid_fr_min=ORIG_FR[i][1]))
        if i in PICK:
            take, method, emo, fr, frmin = PICK[i]
            ex = json.loads((ACC / (take + '.json')).read_text(encoding='utf8'))
            spoken = ex['text']
            new = dict(line=i, speaker=l['speaker'], tags=(TAG + ' ' + emo).strip(), text=l['text'], english=l.get('english', ''),
                       spoken=spoken, model=ex['body'].get('model_id', 'eleven_v4'), seed=ex['body'].get('seed'), status=200,
                       endpoint='with-timestamps', alignment=ex['alignment'], accent_method=method, source_take=take,
                       lid_fr=fr, lid_fr_min=frmin, replaces='approved take kept in orig/ (detector: ' + str(ORIG_FR[i][0]) + ')')
            shutil.copy2(ACC / (take + '.mp3'), OUT / 'v4' / (stem + '.mp3'))
            new['audio_bytes'] = (OUT / 'v4' / (stem + '.mp3')).stat().st_size
            (OUT / 'v4' / (stem + '.json')).write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding='utf8')
            fixed.append(dict(new, audio=f'v4/{stem}.mp3'))
        else:
            for ext in ('.mp3', '.json'): shutil.copy2(SRC / 'v4' / (stem + ext), OUT / 'v4' / (stem + ext))
            fixed.append(dict(rec, audio=f'v4/{stem}.mp3', lid_fr=ORIG_FR[i][0], lid_fr_min=ORIG_FR[i][1]))
        print(stem, 'NEW ' + PICK[i][0] if i in PICK else 'kept', flush=True)
    lite = lambda fs: [{k: v for k, v in f.items() if k not in ('alignment', 'normalized_alignment')} for f in fs]
    man = dict(name='ab_apples_occ_fv_accentfix', language=base.get('language'), voices=base['voices'], lines=base['lines'],
               note='Seller lines 00/02/04 replaced (they read as Spanish/Italian to the language detector); others = approved takes',
               variants=[dict(id='v4', model='eleven_v4 accent fix', files=lite(fixed)), dict(id='orig', model='eleven_v4 approved', files=lite(orig))])
    for vs in man['variants']:
        for f in vs['files']: f['english'] = (f.get('english') or '') + f"  [French {f['lid_fr']:.2f}]"
    (OUT / 'manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf8')
    (OUT / 'index.html').write_text(PAGE.replace('/*MANIFEST*/null', json.dumps(man, ensure_ascii=False)).replace('Speech mockup: ', 'Accent fix: '), encoding='utf8')
    print('DONE', OUT)

if __name__ == '__main__':
    main()
