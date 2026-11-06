"""ElevenLabs capability probe for the Prophecy gibberish-speech pipeline (run LOCALLY, not in the cloud).

Usage (PowerShell, from the project root):
  $env:ELEVENLABS_API_KEY = '<your key>'      # or set it once as a user environment variable
  & 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/Speech/elevenlabs_probe.py

Standard library only. NEVER prints or writes the API key. Spends about 300-600 characters of credit.
Writes everything to Saved/Speech/probe/ (git-ignored):
  summary.json            account tier/quota, models, voices, which test calls worked, sizes, errors
  <model>__<line>.mp3      test audio
  <model>__<line>.json     timing (alignment) returned by the API, audio stripped out
"""
import base64, json, os, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Saved/Speech/probe'
OUT.mkdir(parents=True, exist_ok=True)
KEY = os.environ.get('ELEVENLABS_API_KEY', '').strip()
API = 'https://api.elevenlabs.io'
summary = {'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'key_present': bool(KEY), 'errors': []}

def call(method, path, body=None, timeout=90):
    req = urllib.request.Request(API + path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={'xi-api-key': KEY, 'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {'error': e.read().decode(errors='replace')[:800]}
    except Exception as e:  # network/proxy/firewall problems
        return None, {'error': repr(e)[:800]}

def save():
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1), encoding='utf8')

if not KEY:
    summary['errors'].append('ELEVENLABS_API_KEY not set'); save(); sys.exit('ELEVENLABS_API_KEY not set (see header)')

# 1. account / quota (needs user_read permission on scoped keys)
st, sub = call('GET', '/v1/user/subscription')
summary['subscription_status'] = st
if st == 200:
    summary['subscription'] = {k: sub.get(k) for k in ('tier', 'status', 'character_count', 'character_limit',
        'next_character_count_reset_unix', 'can_use_instant_voice_cloning', 'can_use_professional_voice_cloning',
        'voice_limit', 'professional_voice_limit')}
else:
    summary['errors'].append(['subscription', st, sub])

# 2. models
st, models = call('GET', '/v1/models')
summary['models_status'] = st
if st == 200:
    summary['models'] = [{k: m.get(k) for k in ('model_id', 'name', 'can_do_text_to_speech', 'max_characters_request_free_user',
                          'max_characters_request_subscribed_user', 'maximum_text_length_per_request')} for m in models]
else:
    summary['errors'].append(['models', st, models])

# 3. voices (names/ids/labels only)
st, voices = call('GET', '/v1/voices')
summary['voices_status'] = st
vlist = voices.get('voices', []) if st == 200 else []
summary['voices'] = [{'voice_id': v.get('voice_id'), 'name': v.get('name'), 'category': v.get('category'),
                      'labels': v.get('labels')} for v in vlist]
if st != 200:
    summary['errors'].append(['voices', st, voices])
save()

# 4. test lines: invented words with fixed spelling rules, plus one emotion-tag test for v3
LINES = {
    'calm': 'Kalaveth oru tamesh, ilvan dor keshari? Nai... sotu varel en mabeth.',
    'angry_tag': '[angry] Drovak! Teshu vorn kalaveth, ilvan dor GARESH!',
}
voice_id = os.environ.get('PROBE_VOICE_ID') or next((v['voice_id'] for v in vlist if v.get('category') == 'premade'), None) \
    or (vlist[0]['voice_id'] if vlist else None)
summary['test_voice_id'] = voice_id
available = {m['model_id'] for m in summary.get('models', []) if m.get('can_do_text_to_speech')}
summary['tests'] = []
for model in ('eleven_multilingual_v2', 'eleven_v3', 'eleven_flash_v2_5'):
    if available and model not in available:
        summary['tests'].append({'model': model, 'skipped': 'not available to this account'}); continue
    for name, text in LINES.items():
        if name == 'angry_tag' and model != 'eleven_v3':
            continue
        body = {'text': text, 'model_id': model}
        st, res = call('POST', f'/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128', body, timeout=180)
        rec = {'model': model, 'line': name, 'status': st, 'chars': len(text)}
        if st == 200 and res.get('audio_base64'):
            audio = base64.b64decode(res['audio_base64'])
            (OUT / f'{model}__{name}.mp3').write_bytes(audio)
            meta = {k: v for k, v in res.items() if k != 'audio_base64'}
            (OUT / f'{model}__{name}.json').write_text(json.dumps(meta, indent=1), encoding='utf8')
            al = res.get('alignment') or {}
            rec.update(audio_bytes=len(audio), has_alignment=bool(al),
                       alignment_keys=sorted(al.keys()) if al else None,
                       duration_s=(al.get('character_end_times_seconds') or [None])[-1])
        else:
            rec['error'] = res.get('error') if isinstance(res, dict) else str(res)[:800]
        summary['tests'].append(rec); save()
        print(model, name, st)
print('PROBE_DONE ->', OUT / 'summary.json')
