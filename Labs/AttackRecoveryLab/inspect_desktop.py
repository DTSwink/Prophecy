"""Capture the registered desktop view and its read-only numerical trajectory."""
import hashlib
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8817'

def get(path):
    with urlopen(URL + path, timeout=3) as response:
        return response.read()

def main():
    for attempt in range(6):
        view = json.loads(get('/desktop-view'))
        if not view.get('ok'):
            raise RuntimeError('No registered desktop publisher')
        try:
            image = get('/desktop-view.png?sequence=' + str(view['sequence']))
        except HTTPError as error:
            if error.code == 409:
                continue
            raise
        if hashlib.sha256(image).hexdigest() != view['imageSha256']:
            raise RuntimeError('The image does not match the desktop state')
        break
    else:
        raise RuntimeError('Desktop changed during every image read')
    health = json.loads(get('/health'))
    if view['state']['revision'] != health['revision']:
        raise RuntimeError('Desktop has not loaded the current build')
    before = json.loads((ROOT / 'changes-v2-before/state-before-activation.json').read_text())
    matches_before = {key: view['state'][key] == before[key]
                      for key in ('attack', 'variant', 'time', 'camera')}
    body = json.dumps({'clientId':view['clientId'],'command':'capture_visible_trajectory'}).encode()
    request = Request(URL + '/app-control', data=body, headers={'Content-Type':'application/json'})
    command = json.loads(urlopen(request, timeout=3).read())
    for attempt in range(40):
        capture = json.loads(get('/capture?id=' + command['id']))
        if not capture.get('pending'):
            break
        time.sleep(.1)
    if capture.get('fingerprint') != command['fingerprint'] or 'samples' not in capture:
        raise RuntimeError('Desktop trajectory capture failed identity check')
    if command['fingerprint'] != view['fingerprint']:
        raise RuntimeError('User changed the desktop during capture; retry without changing their view')
    (ROOT / 'verification-v2-desktop.png').write_bytes(image)
    (ROOT / 'verification-v2-desktop.json').write_text(json.dumps(view, indent=2), encoding='utf-8')
    result = {'ok':True,'clientId':view['clientId'],'frame':view['frame'],
        'attack':view['state']['attack'],'variant':view['state']['variant'],
        'matchesPreUpdateState':matches_before,'revision':view['state']['revision'],
        'readOnlyCaptureSamples':len(capture['samples']),'runtimeErrors':view['runtimeErrors']}
    (ROOT / 'verification-v2-live.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__ == '__main__':
    main()
