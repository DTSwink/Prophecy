"""Small single-thread genuine NN checkpoint test; no live service changes."""
import copy,gzip,json,tempfile,time
from pathlib import Path
from nn_worker import ResumeLocomotion
from directional_nn import configure_direction,generate_command
import surface_nn as sn
ROOT=Path(__file__).resolve().parent
fixture=json.loads(gzip.decompress((ROOT/'snapshots/slide-live-5.json.gz').read_bytes()))
settings=fixture['request']['settings']
started=time.perf_counter()
owner=ResumeLocomotion('run');configure_direction(owner,'run','left')
seed=generate_command(owner,dict(kind='direction',policy='run',gait='run',direction='left',phase=.36,duration=.1,totalDuration=5,seedOnly=True,rootYawSpeed=settings['rootYawSpeed'],rootYawStart=settings['rootYawStart'],rootYawStop=settings['rootYawStop']))
(ROOT/'snapshots/surface-bounded-seed.json').write_text(json.dumps(seed,separators=(',',':')),encoding='utf-8')
print(json.dumps(dict(seedSeconds=time.perf_counter()-started,referenceHeight=seed['directionMeta']['referenceHeight'],poses=len(seed['poses']))),flush=True)
request=copy.deepcopy(fixture['request']);request.update(source=seed,sourceVersion=sn.source_version(),totalDuration=5,endTime=.05,roots=seed['roots'][:12],seeds=[dict(points=[seed['roots'][i],*seed['poses'][i]['points']],axes=[[[1,0,0],[0,1,0],[0,0,1]],*seed['poses'][i]['axes']]) for i in (0,1)])
checks=[]
def check(name,value):
 checks.append(dict(name=name,passed=bool(value)))
 if not value: raise AssertionError(name)
with tempfile.TemporaryDirectory(prefix='footik-live-session-test-') as temp:
 sessions=sn.SurfaceSessions();sessions.folder=Path(temp)
 try:
  a=sessions.process(owner,request);token=a['sessionId'];b=sessions.process(owner,dict(request,sessionId=token,endTime=.2));prefix=copy.deepcopy(b['steps']);sessions.close()
  c=sessions.process(owner,dict(request,sessionId=token,endTime=.3));d=sessions.process(owner,dict(request,endTime=.3,fixtureCase='onepass'))
  check('Only initial source segment is generated',seed['duration']==.1 and len(seed['poses'])<=5 and seed['directionMeta']['totalDuration']==5)
  check('Reference height is stable warmup metadata',.5<seed['directionMeta']['referenceHeight']<1.5)
  check('True recurrent states restore without changing prefix',c['restored'] and c['steps'][:len(prefix)]==prefix)
  check('True split/restored poses and pins equal one-pass exactly',c['steps']==d['steps'])
  check('True split/restored physical root windows equal one-pass',c['diagnostics']['coupling']['windows']==d['diagnostics']['coupling']['windows'])
  check('Only requested tail calls are added',a['appendedInferences']+b['appendedInferences']+c['appendedInferences']==len(c['steps']))
  check('No inferred step begins at or after trim',all(w['frame']<.3*60 for w in c['diagnostics']['coupling']['windows']))
  details=dict(initialCalls=a['appendedInferences'],firstTailCalls=b['appendedInferences'],restoredTailCalls=c['appendedInferences'],totalCalls=len(c['steps']),generatedThrough=c['generatedThrough'])
 finally:sessions.close()
report=dict(passed=True,checks=checks,seconds=time.perf_counter()-started,details=details,referenceHeight=seed['directionMeta']['referenceHeight'],sourceVersion=sn.source_version())
(ROOT/'snapshots/surface-session-live-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
