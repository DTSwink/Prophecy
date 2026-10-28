"""Distance-gated yaw through the actual Run NN and original root encoder."""
import json
import math
from pathlib import Path
from verify_nn_root_window import request

ROOT = Path(__file__).resolve().parent
checks = []
def check(name, ok):
    assert ok, name
    checks.append(name)

for gait, speed in [('walk', 2.), ('run', 5.)]:
    data = request(dict(kind='direction', policy='run', gait=gait, direction='forward',
        duration=5, phase=.21, rootYawSpeed=90, rootYawStart=3, rootYawStop=8, verifyReference=True))
    yaw = lambda t: 90*max(0., min(max(0., speed*t),8)-3)/speed
    check(gait+' unchanged root speed',abs(data['command']['commandSpeed']-speed)<1e-4)
    check(gait+' starts at 3m and stops at 8m',all(abs(value-yaw(i/30))<1e-4 for i,value in enumerate(data['rootYawDegrees'])))
    check(gait+' original NN and root-window parity',data['referenceError']<2e-6 and data['windowReferenceError']<2e-6)
    check(gait+' keeps original continuous pin projection',data['pinDiagnostics']['mode']=='continuous_sigmoid' and data['pinDiagnostics']['projectionChange']>.001)
    features=data['rootFeatures']
    check(gait+' eight future samples anticipate both distance boundaries',all(
        abs(f[3+4*k+2]-math.cos(math.radians(yaw((i+k+1)/30)-yaw(i/30))))<2e-5 and
        abs(f[3+4*k+3]-math.sin(math.radians(yaw((i+k+1)/30)-yaw(i/30))))<2e-5
        for i,f in enumerate(features) for k in range(8)))
    stop_frame=math.ceil(8/speed*30)+1
    check(gait+' heading holds after stop',max(data['rootYawDegrees'][stop_frame:])-min(data['rootYawDegrees'][stop_frame:])<1e-4)
    (ROOT/'snapshots'/('yaw-distance-'+gait+'.json')).write_text(json.dumps(data,separators=(',',':')))
    print(json.dumps(dict(gait=gait,startSeconds=3/speed,stopSeconds=8/speed,finalYaw=yaw(5),seconds=data['seconds'])),flush=True)
(ROOT/'yaw-distance-verification.json').write_text(json.dumps(dict(passed=True,checks=checks),indent=2))
print(f'{len(checks)} checks passed')
