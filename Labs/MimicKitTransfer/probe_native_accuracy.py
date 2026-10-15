"""Same-state native iteration/geometry isolation, no policy feedback."""
import os,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np,mujoco
import native_probe
from native_probe import Native,names
from probe_sequential_contacts import encode,decode


def main():
    out=probe.OUT/'causal_transfer'
    with np.load(out/'body_velocity_engine_cpu_phase0.5625.npz') as z:data={k:z[k] for k in z.files}
    with np.load(out/'phase9_impact_jolt_axes.npz') as z:pred=z['jolt_axes_mj'];steps=z['steps']
    m=mujoco.MjModel.from_binary_path(str(out/'sequential_model.mjb'));rows=[]
    native_probe.fixture_path=probe.OUT/'point-contact/profile/fixture.exe'
    for key in list(os.environ):
        if key.startswith('TRANSFER_'):del os.environ[key]
    os.environ.update(TRANSFER_TRAINING_CONTACT='1',TRANSFER_FRICTIONLESS_SELF='1',TRANSFER_SUBSTEPS='1',TRANSFER_RIG_POSITION_STEPS='20')
    for step in (19,21,31):
        state=data['subin'][step];action=data['actions'][step//8,0].clip(-2*np.pi,2*np.pi)
        d=mujoco.MjData(m);d.qpos[:],d.qvel[:]=encode(m,state);mujoco.mj_forward(m,d)
        contacts=[dict(geom=c.geom.tolist(),distance=float(c.dist),position=c.pos.tolist(),normal=c.frame[:3].tolist()) for c in d.contact if c.dist<0]
        previous=None
        for iterations in (40,100,255):
            os.environ['TRANSFER_RIG_VELOCITY_STEPS']=str(iterations)
            n=Native(state)
            try:result=n.request('step '+' '.join(map(str,action)))
            finally:n.close()
            actual=np.array(result['bodies']);reference=pred[int(np.flatnonzero(steps==step)[0])]
            error=np.linalg.norm(reference[:,10:]-actual[:,10:],axis=-1)
            row=dict(step=step,iterations=iterations,angular_difference=float(error.max()),worst_body=names[int(error.argmax())],
                motor_defect_nm=result['motor_defect_nm'],ground_impulse_ns=sum(result['ground_vertical_impulse_ns']),
                native_contacts=result['contacts'],mj_contacts=contacts)
            if previous is not None:row['change_from_previous_iterations']=float(np.linalg.norm(actual[:,10:]-previous[:,10:],axis=-1).max())
            rows.append(row);previous=actual
            print(json.dumps({k:v for k,v in row.items() if k not in ('native_contacts','mj_contacts')}),flush=True)
    (out/'native_accuracy.json').write_text(json.dumps(rows,indent=2))


if __name__=='__main__':main()
