"""Generate a speech batch with ElevenLabs (run LOCALLY; the cloud session cannot reach the API).

  & 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/Speech/el_generate.py Tools/Speech/batches/mockup1_gate.json
Options: --dry-run (count characters only), --max-chars N (default 3000, refuses bigger batches),
         --variants v3_fr,v4_fr (subset), --force (regenerate lines that already exist).
Key: env ELEVENLABS_API_KEY (falls back to the Windows *user* environment variable). Never printed or written.
Output: Saved/Speech/<batch name>/<variant>/NN_<speaker>.mp3 + .json (text, tags, alignment), manifest.json,
        index.html (local listening page: play each line or the whole scene per variant).
Standard library only.
"""
import argparse, base64, json, os, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = 'https://api.elevenlabs.io'

def api_key():
    k = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if not k and os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as h:
                k = str(winreg.QueryValueEx(h, 'ELEVENLABS_API_KEY')[0]).strip()
        except OSError:
            pass
    return k

def call(key, method, path, body=None, timeout=180):
    for attempt in range(5):
        req = urllib.request.Request(API + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                     headers={'xi-api-key': key, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                ctype = r.headers.get('Content-Type', '')
                return r.status, (json.loads(data.decode()) if 'json' in ctype else data)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors='replace')[:1000]
            if e.code in (429, 500, 502, 503) and attempt < 4:
                time.sleep(2 ** attempt * 2); continue
            return e.code, {'error': msg}
        except Exception as e:
            if attempt < 4: time.sleep(2 ** attempt); continue
            return None, {'error': repr(e)[:500]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('batch'); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--force', action='store_true')
    ap.add_argument('--max-chars', type=int, default=3000); ap.add_argument('--variants', default='')
    a = ap.parse_args()
    batch = json.loads(Path(a.batch).read_text(encoding='utf8'))
    variants = [v for v in batch['variants'] if not a.variants or v['id'] in a.variants.split(',')]
    out = ROOT / 'Saved/Speech' / batch['name']; out.mkdir(parents=True, exist_ok=True)
    spoken = lambda l: (l.get('tags', '') + ' ' + l['text']).strip()
    total = sum(len(spoken(l)) for l in batch['lines']) * len(variants)
    print(f"{batch['name']}: {len(batch['lines'])} lines x {len(variants)} variants = {total} characters")
    if total > a.max_chars: sys.exit(f'Refusing: {total} > --max-chars {a.max_chars}')
    if a.dry_run: return
    key = api_key()
    if not key: sys.exit('ELEVENLABS_API_KEY not found (env or Windows user environment)')
    st, sub0 = call(key, 'GET', '/v1/user/subscription')
    manifest = dict(name=batch['name'], language=batch.get('language'), voices=batch['voices'], variants=[], lines=batch['lines'])
    for v in variants:
        vdir = out / v['id']; vdir.mkdir(exist_ok=True)
        vrec = dict(v, files=[])
        for i, l in enumerate(batch['lines']):
            stem = f"{i:02d}_{l['speaker']}"
            mp3, js = vdir / (stem + '.mp3'), vdir / (stem + '.json')
            if mp3.exists() and js.exists() and not a.force:
                vrec['files'].append(dict(json.loads(js.read_text(encoding='utf8')), audio=f"{v['id']}/{stem}.mp3")); continue
            voice = batch['voices'][l['speaker']]['voice_id']
            body = dict(text=spoken(l), model_id=v['model'])
            if v.get('language_code'): body['language_code'] = v['language_code']
            if v.get('voice_settings'): body['voice_settings'] = v['voice_settings']
            st, res = call(key, 'POST', f'/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128', body)
            rec = dict(line=i, speaker=l['speaker'], tags=l.get('tags', ''), text=l['text'], english=l.get('english', ''),
                       model=v['model'], status=st, endpoint='with-timestamps')
            audio = None
            if st == 200 and isinstance(res, dict) and res.get('audio_base64'):
                audio = base64.b64decode(res['audio_base64'])
                rec['alignment'] = res.get('alignment'); rec['normalized_alignment'] = res.get('normalized_alignment')
            else:
                rec['timestamps_error'] = res.get('error') if isinstance(res, dict) else str(res)[:500]
                st2, res2 = call(key, 'POST', f'/v1/text-to-speech/{voice}?output_format=mp3_44100_128', body)
                rec.update(status=st2, endpoint='plain')
                if st2 == 200 and isinstance(res2, (bytes, bytearray)): audio = bytes(res2)
                else: rec['error'] = res2.get('error') if isinstance(res2, dict) else str(res2)[:500]
            if audio:
                mp3.write_bytes(audio); rec['audio_bytes'] = len(audio)
                js.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf8')
                vrec['files'].append(dict(rec, audio=f"{v['id']}/{stem}.mp3"))
            else:
                vrec['files'].append(rec)
            print(v['id'], stem, rec['status'], rec['endpoint'], rec.get('error', '')[:120])
        manifest['variants'].append(vrec)
    st, sub1 = call(key, 'GET', '/v1/user/subscription')
    if isinstance(sub0, dict) and isinstance(sub1, dict) and 'character_count' in sub1:
        manifest['credits_used'] = sub1['character_count'] - sub0.get('character_count', sub1['character_count'])
        manifest['credits_left'] = sub1['character_limit'] - sub1['character_count']
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf8')
    (out / 'index.html').write_text(PAGE.replace('/*MANIFEST*/null', json.dumps(manifest, ensure_ascii=False)), encoding='utf8')
    print('DONE', out / 'index.html', 'credits used', manifest.get('credits_used'), 'left', manifest.get('credits_left'))

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Speech Mockup</title><style>
:root{--bg:#f6f5f2;--fg:#1d1d1b;--muted:#6b6a66;--card:#fff;--line:#e3e1dc;--accent:#8a3b2e}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe7;--muted:#a3a19b;--card:#21201e;--line:#34322f;--accent:#e08a74}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 20px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.v{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.v h2{font-size:16px;margin:0 0 8px;display:flex;justify-content:space-between;align-items:center}
button{background:var(--accent);color:#fff;border:0;border-radius:6px;padding:6px 12px;cursor:pointer;font:inherit}
.l{border-top:1px solid var(--line);padding:8px 0;cursor:pointer}.l.on{background:color-mix(in srgb,var(--accent) 14%,transparent)}
.who{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}.tx{font-size:16px}.en{color:var(--muted);font-size:13px}
.err{color:var(--accent);font-size:12px}</style></head><body><main>
<h1 id="t"></h1><p class="sub" id="s"></p><div class="cols" id="c"></div></main><script>
const M=/*MANIFEST*/null;const A=new Audio();let q=[],cur=null;
document.getElementById('t').textContent='Speech mockup: '+M.name;
document.getElementById('s').textContent=(M.language||'')+(M.credits_used!=null?' | credits used '+M.credits_used+', left '+M.credits_left:'');
function play(el,src){if(cur)cur.classList.remove('on');cur=el;el.classList.add('on');A.src=src;A.play()}
A.onended=()=>{if(cur)cur.classList.remove('on');const n=q.shift();if(n)setTimeout(()=>play(n.el,n.src),350)};
for(const v of M.variants){const d=document.createElement('div');d.className='v';
 const h=document.createElement('h2');h.textContent=v.id+' ('+v.model+')';const b=document.createElement('button');b.textContent='Play scene';h.appendChild(b);d.appendChild(h);
 const items=[];for(const f of v.files){const l=document.createElement('div');l.className='l';
  const vo=(M.voices[f.speaker]||{}).name||'';l.innerHTML='<div class="who"></div><div class="tx"></div><div class="en"></div>';
  l.children[0].textContent=f.speaker+' - '+vo+' '+(f.tags||'');l.children[1].textContent=f.text;l.children[2].textContent=f.english;
  if(f.audio){l.onclick=()=>{q=[];play(l,f.audio)};items.push({el:l,src:f.audio})}else{const e=document.createElement('div');e.className='err';e.textContent='failed: '+(f.error||f.status);l.appendChild(e)}
  d.appendChild(l)}
 b.onclick=()=>{q=items.slice(1);if(items[0])play(items[0].el,items[0].src)};document.getElementById('c').appendChild(d)}
</script></body></html>"""

if __name__ == '__main__':
    main()
