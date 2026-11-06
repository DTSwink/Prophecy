"""Mockup scene 1: 'The Gate' - 3 speakers, emotions taken from the scene (user strategy: real dialogue -> emotion)."""
import json, sys
sys.path.insert(0, '/home/claude/speech')
from lang import build, Relex

SCENE = [  # speaker, ElevenLabs tags, English line (meaning only; never spoken)
    ('captain', '[shouts]', 'Close the gate! They are coming from the north!'),
    ('scout', '[gasps] [rushed]', 'Captain, I saw them... hundreds, maybe more. They burned the river village.'),
    ('captain', '[angry]', 'Then we hold here. Every man on the wall, now!'),
    ('healer', '[worried]', 'We have no water, and the wounded are still inside.'),
    ('captain', '[sighs]', 'I know. I know... Bring them to the old chapel.'),
    ('scout', '[laughs nervously]', 'The chapel? That roof will fall before the enemy does.'),
    ('healer', '[softly]', 'Then it falls on me, not on them. Help me carry the boy.'),
    ('scout', '[whispers]', 'He is not breathing...'),
    ('healer', '[sad]', 'He is. Barely. Keep your hand on his chest.'),
    ('captain', '[shouts]', 'Archers! Wait for my signal... wait...'),
    ('captain', '[shouts]', 'NOW!'),
    ('scout', '[excited]', 'They are running! The river lords are running!'),
]
# voice candidates from the account's premade list (Codex probe), one per character
VOICES = {
    'captain': ('Adam - Dominant, Firm', None),
    'scout': ('Callum - Husky Trickster', None),
    'healer': ('Lily - Velvety Actress', None),
}

def main(out_path):
    lex = build()
    rl = Relex(lex)
    lines = []
    for spk, tags, en in SCENE:
        text, words = rl.sentence(en)
        lines.append(dict(speaker=spk, tags=tags, english=en, text=text, words=words))
    summ = json.load(open('/mnt/user-data/uploads/Prophecy/Saved/Speech/probe/summary.json'))
    ids = {v['name']: v['voice_id'] for v in summ['voices']}
    voices = {k: dict(name=n, voice_id=ids[n]) for k, (n, _) in VOICES.items()}
    batch = dict(
        name='mockup1_gate', language='French-flavoured invented language (lang.py seed 7)',
        voices=voices,
        variants=[dict(id='v3_fr', model='eleven_v3', language_code='fr'),
                  dict(id='v4_fr', model='eleven_v4', language_code='fr')],
        lines=lines)
    json.dump(batch, open(out_path, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    for l in lines: print(f"{l['speaker']:8s} {l['tags']:22s} {l['text']}")
    chars = sum(len(l['tags']) + 1 + len(l['text']) for l in lines)
    print('characters per variant', chars, 'total', chars * len(batch['variants']))

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/home/claude/speech/mockup1_gate.json')
