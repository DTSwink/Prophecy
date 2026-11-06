"""Accent experiments with ElevenLabs (run LOCALLY with python310; the cloud session cannot reach the API).

  python Tools/Speech/el_accent.py Tools/Speech/accent/<exp>.json [--dry-run] [--max-chars 4000] [--force]
Experiment JSON: {name, voices:{S1:{voice_id}}, defaults:{model, language_code, voice_settings, seed},
                  requests:[{id, speaker, text (exactly what is sent, primer included), prime?, ...body overrides,
                             previous_text?, next_text?}]}
Output: Saved/Speech/accent/<name>/<id>.mp3 + <id>.json (request body minus nothing secret, alignment), manifest.json
Credits are read before/after from /v1/user/subscription; the run refuses if the account would drop under --reserve.
Key: env ELEVENLABS_API_KEY or the Windows user environment (never printed or written). Standard library only.
"""
import argparse, base64, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from el_generate import api_key, call, ROOT   # same key lookup + retrying HTTP helper

BODY_KEYS = ('model_id', 'language_code', 'voice_settings', 'seed', 'previous_text', 'next_text', 'apply_text_normalization')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('exp'); ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true'); ap.add_argument('--max-chars', type=int, default=4000)
    ap.add_argument('--reserve', type=int, default=20000); ap.add_argument('--only', default='')
    a = ap.parse_args()
    E = json.loads(Path(a.exp).read_text(encoding='utf8'))
    reqs = [r for r in E['requests'] if not a.only or r['id'] in a.only.split(',')]
    out = ROOT / 'Saved/Speech/accent' / E['name']; out.mkdir(parents=True, exist_ok=True)
    todo = [r for r in reqs if a.force or not (out / (r['id'] + '.mp3')).exists()]
    chars = sum(len(r['text']) for r in todo)
    print(f"{E['name']}: {len(todo)}/{len(reqs)} requests to make, {chars} characters")
    if chars > a.max_chars: sys.exit(f'Refusing: {chars} > --max-chars {a.max_chars}')
    if a.dry_run or not todo: return
    key = api_key()
    if not key: sys.exit('ELEVENLABS_API_KEY not found')
    st, sub0 = call(key, 'GET', '/v1/user/subscription')
    left0 = sub0['character_limit'] - sub0['character_count'] if isinstance(sub0, dict) and 'character_limit' in sub0 else None
    print('credits left before', left0, 'tier', sub0.get('tier') if isinstance(sub0, dict) else '?')
    if left0 is not None and left0 - chars < a.reserve: sys.exit(f'Refusing: would leave {left0 - chars} < reserve {a.reserve}')
    D = E.get('defaults', {})
    for r in todo:
        body = {'text': r['text'], 'model_id': r.get('model_id', D.get('model_id', 'eleven_v4'))}
        for k in BODY_KEYS[1:]:
            v = r.get(k, D.get(k))
            if v is not None: body[k] = v
        voice = r.get('voice_id') or E['voices'][r['speaker']]['voice_id']
        st, res = call(key, 'POST', f'/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128', body)
        rec = dict(r, body={k: v for k, v in body.items() if k != 'text'}, status=st)
        if st == 200 and isinstance(res, dict) and res.get('audio_base64'):
            audio = base64.b64decode(res['audio_base64'])
            (out / (r['id'] + '.mp3')).write_bytes(audio)
            rec['alignment'] = res.get('alignment'); rec['audio_bytes'] = len(audio)
        else:
            rec['error'] = (res.get('error') if isinstance(res, dict) else str(res))[:600]
        (out / (r['id'] + '.json')).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf8')
        print(r['id'], st, rec.get('error', '')[:200], flush=True)
    st, sub1 = call(key, 'GET', '/v1/user/subscription')
    if isinstance(sub1, dict) and 'character_limit' in sub1:
        left1 = sub1['character_limit'] - sub1['character_count']
        print('credits used', (left0 - left1) if left0 is not None else '?', 'left', left1)

if __name__ == '__main__':
    main()
