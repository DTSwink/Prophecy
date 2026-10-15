"""Separate velocity solve from movement of the articulated coordinate frame.

Read-only use of preserved, identical-incoming-state one-substep results.
No stale velocities are fed to the policy or used as a proposed fix.
"""
import os,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np,mujoco
from probe_sequential_contacts import encode,decode
from native_probe import names


def main():
    out=probe.OUT/'causal_transfer'
    with np.load(out/'body_velocity_engine_cpu_phase0.5625.npz') as z:incoming=z['subin']
    with np.load(out/'phase9_impact_jolt_axes.npz') as z:data={k:z[k] for k in z.files}
    m=mujoco.MjModel.from_binary_path(str(out/'sequential_model.mjb'))
    report=[]
    for case in ('manifolds','jolt_axes'):
        for i,step in enumerate(data['steps']):
            pred=data[case+'_mj'][i];native=data[case+'_jolt'][i]
            qin,vin=encode(m,incoming[step]);qout,vout=encode(m,pred)
            d=mujoco.MjData(m);d.qpos[:]=qout;d.qvel[:]=vout
            np.testing.assert_allclose(decode(m,d)[:,7:],pred[:,7:],atol=1e-5)
            d.qpos[:]=qin;before=decode(m,d)
            physical=np.linalg.norm(pred[:,10:]-native[:,10:],axis=-1)
            before_error=np.linalg.norm(before[:,10:]-native[:,10:],axis=-1)
            transport=np.linalg.norm(pred[:,10:]-before[:,10:],axis=-1)
            row=dict(case=case,step=int(step),physical_max=float(physical.max()),
                at_incoming_pose_max=float(before_error.max()),
                frame_transport_max=float(transport.max()),
                worst_body=names[int(physical.argmax())],
                physical_foot=float(physical[names.index('right_foot')]),
                incoming_pose_foot=float(before_error[names.index('right_foot')]))
            report.append(row)
    (out/'velocity_transport.json').write_text(json.dumps(report,indent=2))
    for case in ('manifolds','jolt_axes'):
        rows=[r for r in report if r['case']==case]
        print(json.dumps(dict(case=case,physical_max=max(r['physical_max'] for r in rows),
            incoming_pose_max=max(r['at_incoming_pose_max'] for r in rows),
            impact=[r for r in rows if r['step'] in (19,21,31)])),flush=True)


if __name__=='__main__':main()
