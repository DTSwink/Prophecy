"""Control for the UE world-basis rotation, without changing controller inputs."""
import json
import os
import numpy as np
from scipy.spatial.transform import Rotation as R
import AuditTransfer as audit

os.environ['AUDIT_FIXTURE'] = str(audit.OUT/'point/fixture.exe')
os.environ['AUDIT_DLL_DIR'] = str(audit.ROOT/'Intermediate/JoltMigration/Install/Development/bin')
basis = R.from_euler('z', -90, degrees=True)
def rotate(state, rotation):
    out=state.copy();out[:,:3]=rotation.apply(state[:,:3]);out[:,3:7]=(rotation*R.from_quat(state[:,3:7])).as_quat()
    out[:,7:10]=rotation.apply(state[:,7:10]);out[:,10:13]=rotation.apply(state[:,10:13]);return out

results=[]
for row in json.loads((audit.OUT/'directions.json').read_text()):
    seed=np.load(audit.ROOT/f"Saved/Diagnostics/RobotLocomotion20261026/native-case{row['case']}.npz")
    angle=np.deg2rad(row['direction_deg']);direction=np.array([np.cos(angle),np.sin(angle)])
    for backend in ('mujoco','jolt'):
        phase=seed['phases'][420].copy();state=rotate(seed['states'][420],basis)
        sim=audit.Jolt(state,{'CAND_SPHERICAL':'1','CAND_LIMIT_HZ':'32'}) if backend=='jolt' else audit.ref.reset(state)
        if backend=='jolt':state=sim.state
        else:state=audit.ref.read(sim)
        start=rotate(state,basis.inv());minimum=state[0,2]
        try:
            for tick in range(150):
                action,phase=audit.policy(rotate(state,basis.inv()),phase,direction)
                if backend=='jolt':state=sim.step(action)
                else:
                    sim.ctrl[:]=0;sim.ctrl[audit.ref.velocity_motors]=action
                    for _ in range(8):audit.ref.mujoco.mj_step(audit.ref.model,sim)
                    audit.ref.mujoco.mj_forward(audit.ref.model,sim);state=audit.ref.read(sim)
                minimum=min(minimum,state[0,2])
        finally:
            if backend=='jolt':sim.close()
        end=rotate(state,basis.inv());travel=float((end[0,:2]-start[0,:2])@direction)
        result=dict(case=row['case']*8+row['direction_deg']//45,backend=backend,
                    min_pelvis_cm=float(minimum*100),travel_cm=travel*100,passed=bool(minimum>=.6 and travel>1))
        results.append(result);print(json.dumps(result),flush=True)
        (audit.OUT/'rotated-contacts.json').write_text(json.dumps(results,indent=2))
(audit.OUT/'rotated-contacts.json').write_text(json.dumps(results,indent=2))
