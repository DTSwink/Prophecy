"""Independent derivatives and dynamic tests for the PHAT limit extension."""
from pathlib import Path
import json
import numpy as np
from scipy.spatial.transform import Rotation as R
import mujoco
import mujoco_warp as mjw
import warp as wp
from phat_constraints import PhatConstraints,coordinates,coordinate_gradients

OUT=Path(__file__).resolve().parents[2]/"Saved/Robotics"

@wp.kernel
def sample(qs:wp.array(dtype=wp.quat),values:wp.array(dtype=wp.vec3),gradients:wp.array2d(dtype=wp.vec3)):
    i=wp.tid(); q=qs[i]
    values[i]=coordinates(q)
    t,y,z=coordinate_gradients(q)
    gradients[i,0]=t; gradients[i,1]=y; gradients[i,2]=z

def reference(q):
    w,x,y,z=np.moveaxis(q,-1,0); n=np.sqrt(w*w+x*x)
    t=(2*np.arctan2(x,w)+np.pi)%(2*np.pi)-np.pi
    return np.stack([t,(w*y-x*z)/n,(x*y+w*z)/n],axis=-1)

def test_derivatives():
    rng=np.random.default_rng(731)
    q=R.from_rotvec(rng.normal(size=(1000,3))*.55).as_quat()
    q=q[:,[3,0,1,2]]
    qa=wp.array(q.astype(np.float32),dtype=wp.quat,device="cuda:0")
    va=wp.empty(1000,dtype=wp.vec3,device="cuda:0")
    ga=wp.empty((1000,3),dtype=wp.vec3,device="cuda:0")
    wp.launch(sample,dim=1000,inputs=[qa,va,ga],device="cuda:0")
    values=va.numpy(); grads=ga.numpy()
    finite=[]; eps=1e-6
    rot=R.from_quat(q[:,[1,2,3,0]])
    for axis in np.eye(3):
        plus=(rot*R.from_rotvec(axis*eps)).as_quat()[:,[3,0,1,2]]
        minus=(rot*R.from_rotvec(-axis*eps)).as_quat()[:,[3,0,1,2]]
        finite.append((reference(plus)-reference(minus))/(2*eps))
    finite=np.stack(finite,axis=-1)
    error=float(np.max(np.abs(grads-finite)))
    value_error=float(np.max(np.abs(values-reference(q))))
    assert error<2e-5,(error,value_error)
    assert value_error<2e-6,value_error
    return {"samples":1000,"derivative_max_error":error,"coordinate_max_error":value_error}

def test_dynamics():
    xml='''<mujoco><option gravity="0 0 0" timestep=".0041666666667" iterations="50" tolerance="1e-9"/>
    <worldbody><body><joint name="joint" type="ball" limited="false" solreflimit=".01 1"/>
    <geom type="box" size=".1 .08 .06" mass="1" contype="0" conaffinity="0"/></body></worldbody></mujoco>'''
    reports=[]
    for name,modes in (("three_limited",[1,1,1]),("hinge",[2,2,1]),("locked_twist",[2,1,1])):
        m=mujoco.MjModel.from_xml_string(xml); d=mujoco.MjData(m)
        q=R.from_euler("xyz",[35,32,30],degrees=True).as_quat()[[3,0,1,2]]
        d.qpos[:]=q; mujoco.mj_forward(m,d)
        with wp.ScopedDevice("cuda:0"):
            wm=mjw.put_model(m); wd=mjw.put_data(m,d,nworld=4,nconmax=1,njmax=24)
            ext=PhatConstraints(m,wm,{"joints":[{"name":"joint","modes":modes,"limits_rad":np.deg2rad([20,25,30]).tolist()}]})
            mjw.step(wm,wd)
            with wp.ScopedCapture() as cap: mjw.step(wm,wd)
            for _ in range(480): wp.capture_launch(cap.graph)
            wp.synchronize()
            final=reference(wd.qpos.numpy()); ne=wd.ne.numpy(); count=wd.nefc.numpy()
        assert np.isfinite(final).all()
        for a,mode in enumerate(modes):
            if mode==2: assert np.max(np.abs(final[:,a]))<.001,(name,final)
        if modes[0]==1: assert np.max(np.abs(final[:,0]))<np.deg2rad(20.2),(name,final)
        if modes[1]==modes[2]==1:
            radius=np.sqrt((final[:,1]/np.sin(np.deg2rad(25)/2))**2+(final[:,2]/np.sin(np.deg2rad(30)/2))**2)
            assert radius.max()<1.005,(name,radius,final)
        reports.append({"case":name,"final_coordinates":final[0].tolist(),"equality_rows":int(ne[0]),"total_rows":int(count[0])})
    return reports

if __name__=="__main__":
    wp.init()
    report={"derivatives":test_derivatives(),"dynamics":test_dynamics(),"passed":True}
    (OUT/"phat-constraint-tests.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
