"""ElevenLabs helper tools (run LOCALLY through Saved/ClaudeJobs). Standard library only; key from env / Windows user env.

  el_tools.py search-voices <out.json> [language] [gender]      list shared library voices (no credits)
  el_tools.py add-voice <public_owner_id> <voice_id> <name>      add a library voice to the account (uses a slot)
  el_tools.py sts <voice_id> <in_audio> <out.mp3> [model]        speech-to-speech (voice changer)
  el_tools.py sts-batch <jobs.json>                              many sts jobs: [{"voice_id","in","out"}]
  el_tools.py voices <out.json>                                  list voices on the account
  el_tools.py add-voices <batch.json> S1=<owner>/<voice_id>/<name> ...   add library voices (or reuse already added
                                                                 ones by name) and write their ids into the batch
"""
import json, os, sys, time, uuid, urllib.error, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = 'https://api.elevenlabs.io'

def key():
    k = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if not k and os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as h:
                k = str(winreg.QueryValueEx(h, 'ELEVENLABS_API_KEY')[0]).strip()
        except OSError:
            pass
    if not k: sys.exit('ELEVENLABS_API_KEY not found')
    return k

def req(method, path, body=None, headers=None, timeout=180, raw=False):
    h = {'xi-api-key': key()}; h.update(headers or {})
    if isinstance(body, dict): body = json.dumps(body).encode(); h['Content-Type'] = 'application/json'
    for attempt in range(4):
        r = urllib.request.Request(API + path, data=body, method=method, headers=h)
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                data = resp.read()
                return resp.status, (data if raw else json.loads(data.decode() or '{}'))
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors='replace')[:1500]
            if e.code in (429, 500, 502, 503) and attempt < 3: time.sleep(3 * (attempt + 1)); continue
            return e.code, {'error': msg}
        except Exception as e:
            if attempt < 3: time.sleep(2); continue
            return None, {'error': repr(e)}

def multipart(fields, files):
    b = uuid.uuid4().hex; out = b''
    for k, v in fields.items():
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, (fname, data, ctype) in files.items():
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fname}"\r\nContent-Type: {ctype}\r\n\r\n'.encode() + data + b'\r\n'
    out += f'--{b}--\r\n'.encode()
    return out, {'Content-Type': f'multipart/form-data; boundary={b}'}

def sts(voice, src, dst, model='eleven_multilingual_sts_v2'):
    data = Path(src).read_bytes()
    ctype = 'audio/wav' if src.lower().endswith('.wav') else 'audio/mpeg'
    body, hdr = multipart({'model_id': model, 'remove_background_noise': 'false'}, {'audio': (Path(src).name, data, ctype)})
    st, res = req('POST', f'/v1/speech-to-speech/{voice}?output_format=mp3_44100_128', body, hdr, raw=True)
    if st == 200 and isinstance(res, (bytes, bytearray)):
        Path(dst).parent.mkdir(parents=True, exist_ok=True); Path(dst).write_bytes(res)
    return st, (None if st == 200 else res)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'search-voices':
        out, lang = sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else 'fr')
        gender = sys.argv[4] if len(sys.argv) > 4 else ''
        res_all = []
        for g in ([gender] if gender else ['male', 'female']):
            q = urllib.parse.urlencode(dict(page_size=60, language=lang, gender=g, sort='usage_character_count_1y'))
            st, res = req('GET', f'/v1/shared-voices?{q}')
            print('search', g, st, (res.get('error', '')[:300] if isinstance(res, dict) and 'error' in res else ''))
            for v in (res.get('voices', []) if isinstance(res, dict) else []):
                res_all.append({k: v.get(k) for k in ('public_owner_id', 'voice_id', 'name', 'gender', 'age', 'accent', 'language', 'locale',
                                                       'descriptive', 'use_case', 'category', 'description', 'preview_url',
                                                       'usage_character_count_1y', 'cloned_by_count', 'free_users_allowed', 'verified_languages')})
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(res_all, ensure_ascii=False, indent=1), encoding='utf8'); print('voices', len(res_all), '->', out)
    elif cmd == 'add-voice':
        owner, vid, name = sys.argv[2:5]
        st, res = req('POST', f'/v1/voices/add/{owner}/{vid}', {'new_name': name})
        print('add-voice', st, json.dumps(res)[:500])
    elif cmd == 'add-voices':
        bpath = Path(sys.argv[2]); batch = json.loads(bpath.read_text(encoding='utf8'))
        st, mine = req('GET', '/v1/voices')
        have = {v['name']: v['voice_id'] for v in (mine.get('voices', []) if isinstance(mine, dict) else [])}
        for arg in sys.argv[3:]:
            spk, spec = arg.split('=', 1); owner, vid, name = spec.split('/', 2)
            if name in have: new_id = have[name]; print('voice already on account', spk, name, new_id)
            else:
                st, res = req('POST', f'/v1/voices/add/{owner}/{vid}', {'new_name': name})
                print('add-voice', spk, name, st, (json.dumps(res)[:300] if st != 200 else ''))
                if st != 200: sys.exit('could not add voice ' + name)
                new_id = res.get('voice_id', vid)
            batch['voices'][spk] = dict(batch['voices'].get(spk, {}), name=name, voice_id=new_id)
        bpath.write_text(json.dumps(batch, ensure_ascii=False, indent=1), encoding='utf8'); print('batch voices', batch['voices'])
    elif cmd == 'voices':
        st, res = req('GET', '/v1/voices')
        Path(sys.argv[2]).write_text(json.dumps([{k: v.get(k) for k in ('voice_id', 'name', 'category', 'labels')} for v in res.get('voices', [])],
                                                ensure_ascii=False, indent=1), encoding='utf8'); print('voices', st)
    elif cmd == 'sts':
        st, err = sts(sys.argv[2], sys.argv[3], sys.argv[4], *(sys.argv[5:6]))
        print('sts', st, (json.dumps(err)[:500] if err else 'ok'))
    elif cmd == 'sts-batch':
        jobs = json.loads(Path(sys.argv[2]).read_text(encoding='utf8'))
        for j in jobs:
            st, err = sts(j['voice_id'], str(ROOT / j['in']), str(ROOT / j['out']), j.get('model', 'eleven_multilingual_sts_v2'))
            print('sts', j['out'], st, (json.dumps(err)[:300] if err else 'ok'), flush=True)
    st, sub = req('GET', '/v1/user/subscription')
    if st == 200: print('credits left', sub['character_limit'] - sub['character_count'])
