"""Bounded HTTP integration checks; no scene writes, one CPU inference worker."""
import json
import math
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8890/resume'


def request(payload):
    try:
        with urllib.request.urlopen(urllib.request.Request(URL, json.dumps(payload).encode(),
                                   {'Content-Type': 'application/json'}), timeout=100) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(error.read().decode()) from error


def main():
    checks, cases = [], []
    def check(name, passed):
        assert passed, name
        checks.append(name)
    for gait, direction, omega, speed in [('walk','forward',0,2), ('walk','forward',30,2),
            ('run','left',300,3.5), ('run','backward',-45,3), ('walk','right',-30,1.8)]:
        label = f'{gait}-{direction}-{omega}'
        data = request(dict(kind='direction', policy='run', gait=gait, direction=direction,
                            rootYawSpeed=omega, phase=.21, duration=5, verifyReference=True))
        check(label+' Run checkpoint',data['directionMeta']['policyGait']=='run' and data['source'].startswith('Run 181751'))
        check(label+' original controller parity', data['referenceError'] < 2e-6)
        check(label+' original training root encoder parity',data['windowReferenceError'] < 2e-6)
        check(label+' continuous learned pin projection active',data['pinDiagnostics']['mode']=='continuous_sigmoid'
              and data['pinDiagnostics']['maximum']>.5 and data['pinDiagnostics']['projectionChange']>1e-4)
        check(label+' correct command speed', abs(data['command']['commandSpeed']-speed)<1e-4)
        check(label+' travel does not steer',all(abs(p[0])<1e-6 and abs(p[1])<1e-6 and abs(p[2]-i*speed/30)<1e-4
                                                 for i,p in enumerate(data['roots'])))
        check(label+' root yaw command',all(abs(y-omega*i/30)<.001 for i,y in enumerate(data['rootYawDegrees'])))
        features=data['rootFeatures']
        check(label+' all eight future rotations', all(abs(f[3+4*k+2]-math.cos(math.radians(omega*(k+1)/30)))<2e-5
            and abs(f[3+4*k+3]-math.sin(math.radians(omega*(k+1)/30)))<2e-5 for f in features for k in range(8)))
        check(label+' finite articulated output',all(math.isfinite(v) for p in data['poses'] for row in p['points'] for v in row))
        # A learned pelvis may sway; it must not explode during a full turn.
        heights=[p['points'][0][1] for p in data['poses']]
        check(label+' bounded pelvis',min(heights)>.35 and max(heights)<1.5)
        path=ROOT/'snapshots'/('nn-window-'+label+'.json')
        path.write_text(json.dumps(data,separators=(',',':')))
        cases.append(dict(case=label,seconds=data['seconds'],cache=data['cache'],pin=data['pinDiagnostics'],
                          pelvisHeight=[min(heights),max(heights)],windowError=data['windowReferenceError']))
        print(json.dumps(cases[-1]),flush=True)
    # The upcoming turn must affect inference BEFORE the visible root starts
    # turning, unlike a post-inference spin (whose time-zero pose is unchanged).
    straight=json.loads((ROOT/'snapshots/nn-window-walk-forward-0.json').read_text())
    turning=json.loads((ROOT/'snapshots/nn-window-walk-forward-30.json').read_text())
    anticipation=max(abs(a-b) for pa,pb in zip(straight['poses'][0]['points'],turning['poses'][0]['points']) for a,b in zip(pa,pb))
    check('future yaw changes the time-zero inferred pose',anticipation>1e-4)
    result=dict(passed=True,checks=checks,cases=cases,anticipationMetres=anticipation)
    (ROOT/'nn-root-window-verification.json').write_text(json.dumps(result,indent=2))
    print(f'{len(checks)} checks passed',flush=True)


if __name__=='__main__':
    main()
