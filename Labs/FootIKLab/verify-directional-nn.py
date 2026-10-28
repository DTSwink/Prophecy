"""One serialized, single-thread CPU verification pass; no running lab touched."""
import json
import math
import os
import sys
import time
from pathlib import Path

for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True
from directional_nn import DirectionalLocomotion, generate, torch, validate

ROOT = Path(__file__).resolve().parent
checks, cases = [], []


def check(name, value):
    if not value:
        raise AssertionError(name)
    checks.append(name)


began = time.perf_counter()
for gait in ('walk', 'run'):
    for direction in ('backward', 'left', 'right'):
        if '--run-sides' in sys.argv and (gait != 'run' or direction == 'backward'):
            continue
        model = DirectionalLocomotion(gait, direction)
        request = dict(gait=gait, direction=direction, duration=5, phase=.21, verifyReference=True)
        result = generate(model, request)
        p = torch.tensor([v['points'] for v in result['poses']])
        r = torch.tensor([v['axes'] for v in result['poses']])
        roots = torch.tensor(result['roots'])
        prefix = gait + '/' + direction + ' '
        check(prefix+'bounded finite actual NN poses', len(p) == 152 and bool(torch.isfinite(p).all()))
        check(prefix+'original lower-controller equivalence', result['referenceSamples'] == 3 and result['referenceError'] < 2e-6)
        check(prefix+'both policies ran autoregressively after correct source seed',
              result['lowerInferences'] > 200 and result['upperInferences'] > 150
              and result['command']['relative'].endswith({'backward':'_B.npz','left':'_LR.npz','right':'_RL.npz'}[direction]))
        delta = roots[-1]-roots[0]
        check(prefix+'course travels +Z without lateral drift', float(delta[2]) > 0 and abs(float(delta[0])) < .001)
        speed = float(delta[2]) / ((len(roots)-1)/30)
        check(prefix+'native commanded speed retained', abs(speed-result['command']['commandSpeed']) < .001)
        if gait == 'run' and direction != 'backward':
            check(prefix+'matches native LR/RL 350cm/s command', abs(speed-3.5) < .001)
        facing = result['command']['facingDegrees']
        check(prefix+'body heading remains independent from travel',
              abs(abs(facing)-(180 if direction == 'backward' else 90)) < .01)
        rotation_error = float((r @ r.transpose(-1,-2)-torch.eye(3)).abs().max())
        check(prefix+'proper rigid orientation', rotation_error < 1e-4 and float(torch.linalg.det(r).min()) > .9999)
        cache = ROOT/'.nn-cache'; cache.mkdir(exist_ok=True)
        target = cache/f'directional-{gait}-{direction}.json'
        target.write_text(json.dumps(result, separators=(',', ':'), allow_nan=False), encoding='utf-8')
        case = dict(gait=gait, direction=direction, command=result['command'], speed=speed,
                    seconds=result['seconds'], referenceError=result['referenceError'],
                    fixture=str(target), frames=len(p), maxRotationMatrixError=rotation_error)
        cases.append(case)
        print(json.dumps(case), flush=True)
        if direction == 'backward':
            # A phase changes the initial point in this same continuous lower
            # rollout, not speed/time reversal or an unrelated authored playback.
            other = generate(model, dict(request, duration=.2, phase=.5))
            shift = other['sourceStartFrame']-result['sourceStartFrame']
            a = torch.tensor(other['poses'][0]['points'])
            b = p[shift]
            an = a-torch.tensor(other['roots'][0])
            bn = b-roots[shift]
            slots = [result['names'].index(n) for n in ('foot_l','foot_r','ball_l','ball_r')]
            check(prefix+'phase advances same lower NN gait', float((an[slots]-bn[slots]).abs().max()) < 2e-5)
        del model

for request in (dict(direction='reverse-file'), dict(duration=30), dict(phase=float('nan'))):
    rejected = False
    try:
        validate(request)
    except ValueError:
        rejected = True
    check('reject '+str(request), rejected)

receipt = dict(checks=checks, count=len(checks), cases=cases,
    seconds=time.perf_counter()-began, threads=torch.get_num_threads(), cudaUsed=False)
target = ROOT/('directional-nn-run-sides-verification.json' if '--run-sides' in sys.argv else 'directional-nn-verification.json')
target.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(dict(passed=len(checks), seconds=receipt['seconds'], threads=receipt['threads'])), flush=True)
