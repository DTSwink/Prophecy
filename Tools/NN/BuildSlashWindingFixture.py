"""Independent geometric selection oracle for native FK return verification.

Requires ExportFKReturnLab.cjs --reference-only and numpy/scipy in stepper Python.
The console diagnostic checks native old/new sampling without starting automation.
"""
import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R

project=pathlib.Path(__file__).resolve().parents[2]
lab=json.loads((project/'Saved/FKReturn/lab-reference.json').read_text())
names=lab['names'];parents=lab['parents']
idle=R.from_quat([-.1358083084,.5099821928,.04837901846,.8480175334])
left={'slashl','slashlu','slashld'};right={'slashr','slashru','slashrd'}

def case(label,attack,previous,current,frame):
    i=names.index('upperarm_r');j=names.index('lowerarm_r');s=names.index('spine_05')
    cur=np.array(current);shaft=cur[j,4:]-cur[i,4:]
    inward=R.from_quat(cur[s,:4]).inv().apply(shaft)[2]<-1e-4*np.linalg.norm(shaft)
    delta=((R.from_quat(cur[parents[i],:4])*idle)*R.from_quat(cur[i,:4]).inv()).as_rotvec()
    angle=np.linalg.norm(delta);omega=delta/max(angle,1e-30)
    # Change of horizontal bearing, evaluated in the actual world frame.
    ws=R.from_quat(frame).apply(shaft);wo=R.from_quat(frame).apply(omega)
    sweep=np.cross(ws,np.cross(wo,ws))[2]
    direction=1 if attack.lower() in left else -1 if attack.lower() in right else 0
    changed=bool(direction and inward and angle>2e-5 and direction*sweep<-1e-4*np.dot(shaft,shaft))
    return dict(id=label,attack=attack,names=names,parents=parents,previous=previous,current=current,
                frame=frame,change=changed)

cases=[]
for c in lab['cases']:
    # Exported lab uses -Y up; its carrier maps that direction to Unreal +Z.
    frame=R.from_rotvec([-np.pi/2,0,0]).as_quat().tolist()
    cases.append(case(f"lab/{c['name']}/{c['variant']}",c['name'],c['previous'],c['current'],frame))
record=json.loads((project/'Tools/NN/Fixtures/SlashLReturnWinding.json').read_text())
for attack in [c['name'] for c in lab['cases'][::20]]:
    cases.append(case('captured/'+attack,attack,record['previous'],record['current'],[0,0,0,1]))
for angle in [-179,-90,0,90,179]:
    rotation=R.from_rotvec([0,0,np.radians(angle)])
    def rotate(pose):
        return [(rotation*R.from_quat(t[:4])).as_quat().tolist()+rotation.apply(t[4:]).tolist() for t in pose]
    cases.append(case('captured/yaw/'+str(angle),'slashL',rotate(record['previous']),rotate(record['current']),[0,0,0,1]))
# Saved right slashes already choose the correct route. Reuse a real inward
# endpoint with the opposite sweep to exercise every right-family correction.
for c in lab['cases']:
    candidate=case('probe','slashR',c['previous'],c['current'],R.from_rotvec([-np.pi/2,0,0]).as_quat().tolist())
    if candidate['change']:
        for attack in ['slashR','slashRU','slashRD']:
            cases.append(case('right-branch/'+attack,attack,c['previous'],c['current'],candidate['frame']))
        break
else:
    raise AssertionError('Missing inward clockwise fixture for right-family branch')
out=project/'Saved/Diagnostics/SlashUnwind20261008';out.mkdir(parents=True,exist_ok=True)
(out/'verification-input.json').write_text(json.dumps(dict(cases=cases),separators=(',',':')))
print(json.dumps({'cases':len(cases),'changed':sum(c['change'] for c in cases),'labChanged':sum(c['change'] for c in cases[:320])}))
