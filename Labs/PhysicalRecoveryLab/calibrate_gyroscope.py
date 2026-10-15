"""Isolate the documented Jolt/MuJoCo gyroscopic-force difference on CPU.

Cancellation is a diagnostic only; no training or gameplay force is changed.
"""
import json
from pathlib import Path
import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

OUT=Path(__file__).resolve().parents[2]/'Saved/Robotics'


def simulate(cancel_gyro):
    model=mujoco.MjModel.from_xml_string('''<mujoco><option timestep="0.004166666666667" gravity="0 0 0" integrator="implicitfast"/>
    <worldbody><body><freejoint/><inertial pos="0 0 0" mass="1" diaginertia=".002 .004 .005"/>
    <geom type="sphere" size=".05" contype="0" conaffinity="0"/></body></worldbody></mujoco>''')
    data=mujoco.MjData(model);data.qvel[3:6]=[5,10,15];result=[]
    for step in range(241):
        rotation=Rotation.from_quat(data.qpos[[4,5,6,3]]);angular=rotation.apply(data.qvel[3:6])
        result.append(np.r_[data.qpos[3:7],angular])
        if cancel_gyro:
            inertia=rotation.as_matrix()@np.diag(model.body_inertia[1])@rotation.as_matrix().T
            data.xfrc_applied[1,3:]=np.cross(angular,inertia@angular)
        if step<240:mujoco.mj_step(model,data)
    return np.array(result)


def errors(a,b):
    rot=(Rotation.from_quat(a[:,[1,2,3,0]]).inv()*Rotation.from_quat(b[:,[1,2,3,0]])).magnitude()
    return {'max_rotation_error_deg':float(np.degrees(rot).max()),
            'max_world_angular_velocity_error_rad_s':float(np.linalg.norm(a[:,4:]-b[:,4:],axis=1).max())}


def main():
    traces=np.loadtxt(OUT/'jolt-free-spin.csv',delimiter=',',skiprows=1)
    off=traces[traces[:,0]==0,2:];on=traces[traces[:,0]==1,2:]
    normal=simulate(False);cancelled=simulate(True)
    report={'physics_hz':240,'inertia_kg_m2':[.002,.004,.005],'initial_world_angular_velocity':[5,10,15],
            'jolt_default_vs_mujoco':errors(off,normal),'jolt_gyro_enabled_vs_mujoco':errors(on,normal),
            'jolt_default_vs_diagnostic_gyro_cancellation':errors(off,cancelled),
            'scope':'One free anisotropic body for1s. No articulated-rig/contact parity or production dynamics change.'}
    assert report['jolt_default_vs_mujoco']['max_rotation_error_deg']>10
    assert report['jolt_default_vs_diagnostic_gyro_cancellation']['max_rotation_error_deg']<1
    report['passed']=True
    (OUT/'gyroscope-calibration.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
