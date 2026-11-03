"""Build a lightweight replay from recorded Unreal poses; does not rerun physics."""
import hashlib
import importlib.util
import json
import math
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('native_shapes', Path(__file__).with_name('render-native-frames.py'))
shapes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shapes)
source = ROOT / 'Saved/Diagnostics/BodyflipPort20261030/NativeHost/Saved/Diagnostics/BodyflipPort20261030'
output = ROOT / 'Saved/Diagnostics/BodyflipFloorReview20261103'
output.mkdir(parents=True, exist_ok=True)
cases = []
inputs=[('agent-saved-jolt.json', 'Floor present'), ('agent-air-saved-jolt.json', 'Floor lowered 1.2 m')]
inputs += [(f'agent-foot-diagnostic-{mode}.json', label) for mode,label in [(1,'Comparison: original friction'),(2,'Comparison: zero foot friction'),(3,'Comparison: foot-to-foot collision off')] if (source/f'agent-foot-diagnostic-{mode}.json').exists()]
inputs += [(str(ROOT/'Saved/Diagnostics/BodyflipFinalPort20261102/initial-native/agent-hand-left-jolt.json'),'Unreal: left-hand push / leg stretch'), ('agent-hand-both-jolt.json','Unreal: two-hand push')]
for filename, label in inputs:
    path = source / filename
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    geometry = []
    for body in data['nativeRigProfile']['bodies']:
        for shape in body['shapes']:
            vertices, faces = shapes.shape_mesh(shape, body, data['nativeRigProfile'].get('foot_front_trim_cm', 0))
            geometry.append(dict(bone=data['names'].index(body['name']), name=body['name'], vertices=vertices.tolist(), faces=faces.tolist()))
    frames = []
    for frame in data['frames']:
        target = shapes.target_pose(frame, data['worldSpace'])
        errors=[dict(row) for row in frame['physical']]
        for a,b in [(18,19),(19,20),(22,23),(23,24)]:
            row=next((r for r in errors if r['name']==data['names'][b]),None)
            if row is not None:row['lengthErrorCm']=math.dist(frame['actualPose']['points'][a],frame['actualPose']['points'][b])-math.dist(target['points'][a],target['points'][b])
        frames.append(dict(time=frame['time'], actual=frame['actualPose'], target=dict(points=target['points'].tolist(), q=[q.tolist() for q in target['q']]), errors=errors))
    worst = max((b['angleRad'], i, b['name']) for i, frame in enumerate(frames) for b in frame['errors'])
    case=dict(label=label, source=str(path.relative_to(ROOT)).replace('\\','/'), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), names=data['names'], floor=data['floor'], geometry=geometry, frames=frames, worst=dict(radians=worst[0], frame=worst[1], bone=worst[2]))
    if 'hand-left' in filename:
        case.update(note='Recorded Unreal simulated left-hand push. At 0.400 s the left calf-to-foot segment is 4.12 cm longer than requested. Purple is the requested pose.',focusTime=.4,focusBone='foot_l')
    elif 'hand-both' in filename:
        case['note']='Recorded Unreal two-hand push. This is a separate native physical recording, not the older lab contact-count assertion.'
    cases.append(case)

# Lab comparisons are explicitly labelled; never present them as simulated Unreal.
labFolder=ROOT/'Saved/Diagnostics/BodyflipOtherReview20261103'
labCases=[]
for filename in ['direct.json','sword.json','incline.json','landing.json']:
    p=labFolder/filename
    if p.exists():labCases.extend(json.loads(p.read_text(encoding='utf-8-sig')))
both=ROOT/'Saved/BodyflipLab/HandReview/both-poses.json'
if both.exists():
    d=json.loads(both.read_text(encoding='utf-8-sig'))
    labCases.append(dict(label='Lab check: two-hand contact count',note='Recorded lab fixture: 90-degree flip then a 50% two-hand push. The check disagrees about the number of usable hand contacts, not a separate desired pose; no target overlay exists.',actualLabel='Recorded lab pose',names=d['names'],focusTime=1.8,focusBone='hand_l',frames=[dict(time=f['time'],actual=f['pose'],target=None) for f in d['frames']]))
space=dict(p=[0,0,0],q=[0,0,0,1],scale=[1,1,1])
template=cases[0]['geometry']
for entry in labCases:
    geometry=list(template); rows=[]
    def convert(p):
        transformed=shapes.target_pose(dict(canonical=dict(pose=p)),space)
        return dict(points=transformed['points'].tolist(),q=[q.tolist() for q in transformed['q']])
    for f in entry['frames']:
        actual=convert(f['actual']); target=convert(f['target']) if f.get('target') else None; errors=[]
        if target:
            for i,name in enumerate(entry['names']):
                a=np.array(actual['q'][i]);b=np.array(target['q'][i]);angle=2*math.acos(min(1,abs(float(a@b))/(np.linalg.norm(a)*np.linalg.norm(b))))
                errors.append(dict(name=name,angleRad=angle,errorCm=math.dist(actual['points'][i],target['points'][i])))
        rows.append(dict(time=f['time'],actual=actual,target=target,errors=errors))
    if 'weapon' in entry:
        w=entry['weapon']; vertices=np.array(w['vertices'])[:,[0,2,1]]*100
        q=shapes.multiply(np.array([math.sqrt(.5),0,0,math.sqrt(.5)]),[0,0,0,1])*[-1,1,-1,1]
        vertices=vertices@shapes.matrix(q)
        geometry.append(dict(bone=w['bone'],name='sword',vertices=vertices.tolist(),faces=w['faces'],color=0xd8e8f0))
    worst=max(((r['angleRad'],i,r['name']) for i,f in enumerate(rows) for r in f['errors']),default=(0,0,entry.get('focusBone','pelvis')))
    case={k:v for k,v in entry.items() if k not in ['frames','weapon']}
    case.update(geometry=geometry,frames=rows,hasReference=rows[0]['target'] is not None,lab=True,worst=dict(radians=worst[0],frame=worst[1],bone=worst[2]),floor=dict(p=[0,0,-20],q=[0,0,0,1],scale=[20,20,.4]))
    if entry.get('surface'):
        surface=entry['surface'];case['floor']=dict(p=[surface['position'][i]*100 for i in [0,2,1]],q=convert(dict(points=[[0,0,0]],q=[surface['rotation']]))['q'][0],scale=[surface['size'][i] for i in [0,2,1]])
        # Platform quaternion transforms a world-space box basis, without the bone basis offset.
        q=surface['rotation'];case['floor']['q']=[-q[0],-q[2],-q[1],q[3]]
    cases.append(case)
result = dict(schema='bodyflip-native-review-v1', units='Unreal world centimetres, Z up', cases=cases)
destination = output / 'replay.json'
destination.write_text(json.dumps(result, separators=(',', ':')), encoding='utf-8')
print(f'{destination}: {destination.stat().st_size} bytes, {sum(len(c["frames"]) for c in cases)} recorded frames')
