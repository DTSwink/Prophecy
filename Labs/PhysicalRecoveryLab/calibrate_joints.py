"""Same inertia, PD equation, targets and authored angular bounds in both engines."""
import json
from pathlib import Path
import numpy as np
import mujoco
import mujoco_warp as mjw
import warp as wp
import torch
from scipy.spatial.transform import Rotation
from mujoco_warp._src import math as mm
from phat_constraints import PhatConstraints

OUT=Path(__file__).resolve().parents[2]/"Saved/Robotics"

@wp.kernel
def control(qpos:wp.array2d(dtype=float),qvel:wp.array2d(dtype=float),force:wp.array2d(dtype=float),target:wp.array(dtype=wp.quat)):
    w=wp.tid()
    q=wp.quat(qpos[w,0],qpos[w,1],qpos[w,2],qpos[w,3])
    error=mm.quat_to_vel(mm.mul_quat(mm.quat_inv(q),target[w]))
    torque=20.0*error-3.0*wp.vec3(qvel[w,0],qvel[w,1],qvel[w,2])
    torque*=wp.min(1.0,20.0/wp.max(wp.length(torque),1.e-8))
    for k in range(3):force[w,k]=torque[k]

def main():
    wp.init()
    stream=torch.cuda.Stream();torch.cuda.set_stream(stream);ws=wp.stream_from_torch(stream);wp.set_stream(ws)
    model=mujoco.MjModel.from_xml_string('''<mujoco><option gravity="0 0 0" timestep=".004166666666666667" integrator="implicitfast" iterations="50"/>
      <worldbody><body pos="0 0 1"><joint name="joint" type="ball"/><inertial pos="0 0 0" mass="1" diaginertia=".1 .2 .3"/>
      <geom type="sphere" size=".05" contype="0" conaffinity="0"/></body></worldbody></mujoco>''')
    wm=mjw.put_model(model);wd=mjw.put_data(model,mujoco.MjData(model),nworld=3,nconmax=4,njmax=20)
    PhatConstraints(model,wm,{"joints":[{"name":"joint","modes":[1,1,1],"limits_rad":np.deg2rad([30,45,25]).tolist()}]})
    target=Rotation.from_rotvec([[.15,.2,-.1],[1.2,0,0],[0,1.2,0]]).as_quat()[:,[3,0,1,2]]
    targets=wp.array(target,dtype=wp.quat,device="cuda:0")
    wm.callback.control=lambda m,d:wp.launch(control,3,inputs=[d.qpos,d.qvel,d.qfrc_applied,targets])
    with wp.ScopedCapture() as capture:mjw.step(wm,wd)
    series=[]
    for tick in range(481):
        series.append(wd.qpos.numpy())
        if tick<480:wp.capture_launch(capture.graph)
    actual=np.array(series)
    jolt=np.loadtxt(OUT/"jolt-joint-response.csv",delimiter=",",skiprows=1)
    report={"cases":[],"physics_hz":240}
    for case in range(3):
        jq=jolt[jolt[:,0]==case,2:6];mq=actual[:,case]
        error=(Rotation.from_quat(jq[:,[1,2,3,0]]).inv()*Rotation.from_quat(mq[:,[1,2,3,0]])).magnitude()*180/np.pi
        report["cases"].append({"name":["unlimited_PD_response","twist_stop","swing_stop"][case],
            "rms_angle_error_deg":float(np.sqrt(np.mean(error**2))),"max_angle_error_deg":float(error.max()),
            "final_angle_error_deg":float(error[-1])})
    # Measured tolerances are reported, never concealed by forcing a matching pose.
    report["passed"]=report["cases"][0]["max_angle_error_deg"]<.25 and max(c["max_angle_error_deg"] for c in report["cases"])<3
    (OUT/"joint-calibration.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    np.savez_compressed(OUT/"joint-calibration.npz",mujoco=actual,jolt=jolt)
    print(json.dumps(report,indent=2))
    assert report["passed"],report

if __name__=="__main__":main()
