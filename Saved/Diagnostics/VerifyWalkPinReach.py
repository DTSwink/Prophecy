import json,pathlib,sys,contextlib,io
p=pathlib.Path(__file__).parent
sys.argv=['verify','left-knee-245']
with contextlib.redirect_stdout(io.StringIO()):import AnalyzeRecoveryKnee as a
def load(tag):return json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())['rows']
base=load('left-knee-245');off=load('left-knee-reach-off');on=load('left-knee-reach')
assert len(base)==len(off)==len(on)
def trace(tag,actor):
 return [x for x in map(json.loads,(p/('FootVibration-nn-'+tag+'.jsonl')).read_text().splitlines()) if x['actor']==actor]
bnn=trace('left-knee-245',base[0]['actor']);fnn=trace('left-knee-reach-off',off[0]['actor'])
assert len(bnn)==len(fnn)
err=max(abs(x-y) for b,f in zip(bnn,fnn) for key in ('lower_input','lower_delta','published_lower','upper_input','upper_delta') for x,y in zip(b[key],f[key]))
poseerr=max(abs(x-y)for b,f in zip(base,off)for bone in b['meshes']['PhysicalMesh']for kind in ('p','q','s')for x,y in zip(b['meshes']['PhysicalMesh'][bone][kind],f['meshes']['PhysicalMesh'][bone][kind]))
print('DISABLED_NN_MAX_ERROR',err,'POSE_MAX_ERROR',poseerr)
assert err==0
assert poseerr<1.e-4
rejected=[]
for row in on:
 pin=row.get('pinning')
 if pin and pin['visible'] and pin['selected'][0]>0 and pin['effective'][0]==0:
  if not rejected or pin['time']!=rejected[-1]['time']:rejected.append(pin)
assert rejected
metrics={}
for tag,rows in (('off',off),('on',on)):
 result=[]
 for frame in (245,246,247,248,249,250,251,252):
  b=rows[frame-1]['meshes']['PhysicalMesh'];prev=rows[frame-2]['meshes']['PhysicalMesh']
  result.append(dict(frame=frame,radius=a.geom(b,'l')[2],**a.step(prev,b,'l')))
 metrics[tag]=result
 print(tag,'radii at pops',[round(x['radius'],4)for x in result if x['frame'] in(246,250)])
assert min(x['radius']for x in metrics['on'])>5
(p/'WalkPinReach-verification.json').write_text(json.dumps(dict(disabled_nn_error=err,disabled_pose_error=poseerr,rejected_left_steps=rejected,frames=metrics),indent=2))
print('PASS: disabled equivalence, actual left pin vetoes, and removal of the two measured full extensions.')
