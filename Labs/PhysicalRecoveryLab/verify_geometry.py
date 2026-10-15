"""Independent support-point check of every exported PHAT collider, including feet."""
import itertools
import json
from pathlib import Path
import numpy as np
import mujoco
from scipy.spatial.transform import Rotation

OUT=Path(__file__).resolve().parents[2]/"Saved/Robotics"

def transform(t):
    return Rotation.from_quat(t["rotation_xyzw"]).as_matrix(),np.array(t["position_cm"])*.01

def main():
    rig=json.loads((OUT/"rig.json").read_text())
    m=mujoco.MjModel.from_xml_path(str(OUT/"uefn.xml"));d=mujoco.MjData(m)
    mujoco.mj_resetDataKeyframe(m,d,0);mujoco.mj_forward(m,d)
    report={"passed":True,"colliders":{},"feet":{}}
    for body in rig["bodies"]:
        br,bp=transform(body["reference"])
        for i,shape in enumerate(body["shapes"]):
            name=f"{body['name']}_shape{i}";gid=m.geom(name).id
            sr,sp=transform(shape["local"]);r=br@sr;p=bp+br@sp
            if shape["kind"]=="box":
                size=np.array(shape["half_extent_cm"])*.01
                local=np.array(list(itertools.product((-1,1),repeat=3)))*size
            elif shape["kind"]=="capsule":
                size=np.array([shape["radius_cm"]*.01,shape["cylinder_length_cm"]*.005])
                local=np.vstack([np.eye(3),-np.eye(3)])*size[0]
                local=np.concatenate([local+[0,0,size[1]],local-[0,0,size[1]]])
            elif shape["kind"]=="sphere":
                size=np.array([shape["radius_cm"]*.01]);local=np.vstack([np.eye(3),-np.eye(3)])*size[0]
            else: raise ValueError(shape["kind"])
            expected=local@r.T+p
            actual=local@d.geom_xmat[gid].reshape(3,3).T+d.geom_xpos[gid]
            error=float(np.max(np.linalg.norm(expected-actual,axis=1))*100)
            size_error=float(np.max(np.abs(m.geom_size[gid,:len(size)]-size))*100)
            assert error<.0001 and size_error<.000001,(name,error,size_error)
            assert m.geom_margin[gid]==0 and m.geom_gap[gid]==0,name
            report["colliders"][name]={"surface_point_error_cm":error,"size_error_cm":size_error}
            if body["name"].startswith("foot"):
                report["feet"][body["name"]]={"shape":"box","full_local_dimensions_cm":(size*200).tolist(),
                    "world_bounds_cm":(np.ptp(expected,axis=0)*100).tolist(),"world_corners_cm":(expected*100).tolist()}
    from provenance import verify_export
    report.update(verify_export())
    (OUT/"geometry-verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"passed":True,"collider_count":len(report["colliders"]),"feet":report["feet"]},indent=2))

if __name__=="__main__":main()
