"""Verify actual directional policy feedback with both history poses, on CPU."""
import json
import os
import sys
import time
from pathlib import Path

for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True
from nn_worker import ResumeLocomotion, torch
from directional_nn import configure_direction, resume_in_course

ROOT = Path(__file__).resolve().parent
checks, cases = [], []


def check(name, value):
    if not value:
        raise AssertionError(name)
    checks.append(name)


for gait, direction in [('walk','backward'), ('run','backward'), ('walk','left'), ('run','right')]:
    if '--run-sides' in sys.argv and (gait,direction) != ('run','right'):
        continue
    source = json.loads((ROOT/'.nn-cache'/f'directional-{gait}-{direction}.json').read_text())
    owner = configure_direction(ResumeLocomotion(gait), gait, direction)
    count, current = 20, 41
    seeds = [dict(points=[source['roots'][i], *source['poses'][i]['points']],
                  axes=[[[1,0,0],[0,1,0],[0,0,1]], *source['poses'][i]['axes']])
             for i in (current-1, current)]
    roots = source['roots'][current-1:current+count+8]
    request = dict(gait=gait, direction=direction, names=['root', *source['names']],
                   seeds=seeds, roots=roots, frames=count, verifyReference=True)
    before = time.perf_counter()
    result = resume_in_course(owner, request)
    elapsed = time.perf_counter()-before
    prefix = gait+'/'+direction+' '
    check(prefix+'exact corrected incoming pose', result['poses'][0] == source['poses'][current])
    check(prefix+'both original controllers match compiled reference', result['referenceError'] == 0 and result['inferences'] == count-1)
    check(prefix+'root direction and speed preserved', result['roots'] == roots[1:count+1])
    points = torch.tensor([p['points'] for p in result['poses']])
    axes = torch.tensor([p['axes'] for p in result['poses']])
    check(prefix+'full finite proper poses', bool(torch.isfinite(points).all()) and float(torch.linalg.det(axes).min()) > .9999)
    relatives = axes[1:] @ axes[:-1].transpose(-1,-2)
    cosine = ((relatives.diagonal(dim1=-2, dim2=-1).sum(-1)-1)/2).clamp(-1,1)
    max_step = float(torch.acos(cosine).max())*180/3.141592653589793
    check(prefix+'no full rotation loop or transition snap', max_step < 40)
    forward = -axes[:,source['names'].index('pelvis'),1]
    mean_heading = forward.mean(0)
    desired = torch.tensor([0,0,-1] if direction == 'backward' else [-1,0,0] if direction == 'left' else [1,0,0], dtype=torch.float32)
    check(prefix+'keeps backward/lateral body facing', float(torch.dot(mean_heading,desired)) > .5)
    # Changing only previous state must alter the subsequent actual NN prediction.
    changed = json.loads(json.dumps(request))
    changed['verifyReference'] = False
    changed['seeds'][0]['points'][1][0] += .01
    altered = resume_in_course(owner, changed)
    sensitivity = float((torch.tensor(altered['poses'][1]['points'])-points[1]).abs().max())
    check(prefix+'uses previous corrected state as recurrent history', sensitivity > 1e-6)
    cases.append(dict(gait=gait,direction=direction,seconds=elapsed,maxPolicyAngularStepDegrees=max_step,
                      previousHistorySensitivity=sensitivity,referenceError=result['referenceError']))
    print(json.dumps(cases[-1]),flush=True)

receipt = dict(count=len(checks),checks=checks,cases=cases,threads=torch.get_num_threads(),cudaUsed=False)
try:
    import psutil
    receipt['workerResidentMiB'] = psutil.Process().memory_info().rss / (1024*1024)
except ImportError:
    pass
target = ROOT/('directional-resume-run-sides-verification.json' if '--run-sides' in sys.argv else 'directional-resume-verification.json')
target.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=len(checks),threads=receipt['threads'],residentMiB=receipt.get('workerResidentMiB'))),flush=True)
