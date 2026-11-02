"""Equal-wall-time summary from full-batch episode counters (no replay sampling)."""
import json, statistics
from pathlib import Path
OUT=Path(__file__).resolve().parents[2]/'Saved/MimicKitLocomotionSweeps/20261024_batch2048'

def summary(data,seconds=900):
    start=data['start'];tags=data['scalars']
    def values(tag,a=0,b=seconds):
        return [(t-start,step,value) for t,step,value in tags.get(tag,[]) if a<=t-start<=b]
    def failure(a,b):
        fails={step:value for _,step,value in values('perturbed_outcome_counts/loco_failures',a,b)}
        eps={step:value for _,step,value in values('perturbed_outcome_counts/loco_episodes',a,b)}
        common=fails.keys()&eps.keys()
        n=sum(eps[k] for k in common);f=sum(fails[k] for k in common)
        return dict(episodes=n,failures=f,percent=100*f/n if n else None,windows=len(common))
    points=values('0_Main/Train_Return')
    tests=values('0_Main/Test_Return')
    tests=[v for i,v in enumerate(tests) if i==0 or v[2]!=tests[i-1][2]]
    allpoints=[v for tag in tags for v in values(tag)]
    last=max(allpoints,default=(0,0,0))
    return dict(scope_seconds=seconds,last_observation_seconds=last[0],last_samples=last[1],
        first_three_minutes=failure(0,180),last_three_minutes=failure(seconds-180,seconds),
        per_three_minutes=[failure(a,min(a+180,seconds)) for a in range(0,seconds,180)],
        measured_samples_per_second=(points[-1][1]-points[0][1])/(points[-1][0]-points[0][0]) if len(points)>1 else None,
        training_return_first=statistics.mean(v[2] for v in points if v[0]<180) if any(v[0]<180 for v in points) else None,
        training_return_last=statistics.mean(v[2] for v in points if v[0]>=seconds-180) if any(v[0]>=seconds-180 for v in points) else None,
        evaluations=tests)

if __name__=='__main__':
    result={}
    seconds=json.loads((OUT/'comparison.json').read_text()).get('training_seconds',900)
    for label in ['baseline','trial']:
        p=OUT/(label+'-data.json')
        if p.exists():result[label]=summary(json.loads(p.read_text()),seconds=seconds)
    (OUT/'comparison-results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
