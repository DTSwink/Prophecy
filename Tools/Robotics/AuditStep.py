"""Compare one 240 Hz interval from identical saved MuJoCo states and commands."""
import AuditTransfer as audit
import numpy as np
import os, json
from scipy.spatial.transform import Rotation as R
ref=audit.ref
os.environ.setdefault('AUDIT_FIXTURE',str(ref.folder/'jolt-native-candidates/fixture.exe'))
source=np.load(ref.ROOT/'Saved/Diagnostics/RobotLocomotion20261026/native-case1.npz')
flags={'TRANSFER_SUBSTEPS':'1','CAND_SPHERICAL':'1','CAND_LIMIT_HZ':'32'}
variants={
    'baseline':({},()),
    'no_drag':({'TRANSFER_NO_DRAG':'1'},()),
    'native_motor_no_drag':({'TRANSFER_NO_DRAG':'1','CAND_NATIVE_MOTOR':'1'},()),
    'no_contact':({'TRANSFER_NO_CONTACT':'1','TRANSFER_NO_DRAG':'1'},('CONTACT',)),
    'no_contact_limits':({'TRANSFER_NO_CONTACT':'1','TRANSFER_NO_DRAG':'1','TRANSFER_NO_LIMITS':'1','CAND_SPHERICAL':None},('CONTACT','LIMIT')),
    'free':({'TRANSFER_NO_CONTACT':'1','TRANSFER_NO_DRAG':'1','TRANSFER_NO_LIMITS':'1','TRANSFER_NO_MOTORS':'1','CAND_SPHERICAL':None},('CONTACT','LIMIT','ACTUATION')),
}
results=[]
original=ref.model.opt.disableflags
for label,(extra,disabled) in variants.items():
    ref.model.opt.disableflags=original
    for name in disabled: ref.model.opt.disableflags|=int(getattr(ref.mujoco.mjtDisableBit,'mjDSBL_'+name))
    samples=[]
    for tick in (420,421,425,430,440,450):
        state=source['states'][tick]; action=source['actions'][tick]
        data=ref.reset(state);data.ctrl[:]=0;data.ctrl[ref.velocity_motors]=action
        ref.mujoco.mj_step(ref.model,data);ref.mujoco.mj_forward(ref.model,data);expected=ref.read(data)
        sim=audit.Jolt(state,flags|extra)
        try:
            actual=sim.step(action); receipt=sim.receipt
        finally: sim.close()
        angle=np.rad2deg((R.from_quat(actual[:,3:7])*R.from_quat(expected[:,3:7]).inv()).magnitude())
        w=np.linalg.norm(actual[:,10:13]-expected[:,10:13],axis=1)
        samples.append(dict(tick=tick,angle_deg=float(angle.max()),angular_velocity_error=float(w.max()),
            worst_body=ref.transfer.names[int(w.argmax())],
            linear_velocity_error=float(np.linalg.norm(actual[:,7:10]-expected[:,7:10],axis=1).max()),
            ground_impulse=receipt['ground_vertical_impulse_ns'],
            motor_saturation=receipt['max_motor_fraction'],native_contacts=int(data.ncon)))
    row=dict(label=label,samples=samples);results.append(row);print(json.dumps(row),flush=True)
ref.model.opt.disableflags=original
(audit.OUT/'one-step.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
