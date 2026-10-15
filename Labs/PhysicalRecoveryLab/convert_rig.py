"""Lossless geometry/mass/connector conversion. Training requires the PHAT limit extension.

MuJoCo bodies use the PHAT child connector frame. A ball joint's quaternion
then has exactly the swing/twist reference used by the Jolt importer.
"""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation as R
import mujoco

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"Saved/Robotics"

def matrix(t):
    if not np.allclose(t["scale"],1,atol=1e-6):
        raise ValueError("Unexpected transform scale; native shapes are already baked")
    m=np.eye(4); m[:3,:3]=R.from_quat(t["rotation_xyzw"]).as_matrix()
    m[:3,3]=np.asarray(t["position_cm"])*.01
    return m

def text(x): return " ".join(f"{v:.12g}" for v in np.asarray(x).ravel())
def quat(m): return R.from_matrix(m[:3,:3]).as_quat()[[3,0,1,2]]
def placement(m): return {"pos":text(m[:3,3]),"quat":text(quat(m))}

def convert(source=OUT/"rig.json"):
    rig=json.loads(source.read_text(encoding="utf-8"))
    assert rig["success"],rig.get("error")
    bodies=rig["bodies"]; joints=rig["joints"]
    incoming={j["child"]:j for j in joints}
    assert len(incoming)==len(joints)==len(bodies)-1
    roots=set(range(len(bodies)))-incoming.keys()
    assert len(roots)==1
    root=roots.pop()
    childframes={i:matrix(incoming[i]["child_frame"]) if i in incoming else np.eye(4) for i in range(len(bodies))}
    reference={i:matrix(b["reference"]) for i,b in enumerate(bodies)}
    xml=ET.Element("mujoco",model="Prophecy original UEFN PHAT")
    ET.SubElement(xml,"compiler",angle="radian",autolimits="true",balanceinertia="false",fusestatic="false")
    option=ET.SubElement(xml,"option",timestep=text([1/240]),gravity="0 0 -9.81",integrator="implicitfast",
                        cone="elliptic",iterations="50",tolerance="1e-8")
    ET.SubElement(option,"flag",filterparent="disable")
    ET.SubElement(xml,"size",njmax="512",nconmax="128")
    visual=ET.SubElement(xml,"visual")
    ET.SubElement(visual,"global",offwidth="1280",offheight="720")
    defaults=ET.SubElement(xml,"default")
    ET.SubElement(defaults,"geom",friction=".7 0 0",condim="3",solref=".02 1",solimp=".9 .95 .001 .5 2")
    world=ET.SubElement(xml,"worldbody")
    ET.SubElement(world,"light",pos="2 -3 4",dir="-.3 .3 -1",diffuse=".8 .8 .8")
    ET.SubElement(world,"geom",name="ground",type="plane",size="10 10 .1",rgba=".16 .2 .26 1")
    contact=ET.SubElement(xml,"contact")
    for a,b in rig["disabled_pairs"]:
        ET.SubElement(contact,"exclude",body1=bodies[a]["name"],body2=bodies[b]["name"])
    metadata={"schema":1,"rig_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
              "training_ready":False,"required_extension":"phat_swing_twist",
              "basis":"Same numerical XYZ/quaternions as project Jolt; cm->m only; quaternion serialization WXYZ.",
              "friction":.7,"restitution":0,"body_frames":{},"joints":[],"reference_qpos":[],
              "connector_position_error_cm":{}}
    visited=set(); nodes={}
    def add_body(i,parent_node):
        if i in visited: raise ValueError("Cycle in PHAT tree")
        visited.add(i)
        b=bodies[i]; c=childframes[i]
        if i==root:
            local=reference[i]
        else:
            j=incoming[i]; p=j["parent"]
            if any(m!=2 for m in j["linear_modes"]):
                raise ValueError(f"{b['name']}: only locked PHAT translations supported")
            pf=matrix(j["parent_frame"])
            local=np.linalg.inv(childframes[p])@pf
            parent_joint=reference[p]@pf
            child_joint=reference[i]@c
            error=np.linalg.norm(parent_joint[:3,3]-child_joint[:3,3])*100
            metadata["connector_position_error_cm"][b["name"]]=float(error)
            if error>.002: raise ValueError(f"{b['name']}: reference connector gap {error} cm")
        node=ET.SubElement(parent_node,"body",name=b["name"],**placement(local)); nodes[i]=node
        if i==root:
            ET.SubElement(node,"freejoint",name="floating_pelvis")
            metadata["reference_qpos"].extend(np.r_[local[:3,3],quat(local)].tolist())
        else:
            j=incoming[i]
            joint_name=b["name"]+"_joint"
            ET.SubElement(node,"joint",name=joint_name,type="ball",limited="false",damping="0",armature="0")
            q=quat(np.linalg.inv(parent_joint)@child_joint)
            metadata["reference_qpos"].extend(q.tolist())
            metadata["joints"].append({"name":joint_name,"body":b["name"],
                "modes":j["angular_modes_twist_swing2_swing1"],
                "limits_rad":np.deg2rad(j["angular_limits_deg_twist_swing2_swing1"]).tolist(),
                "reference_wxyz":q.tolist(),"source_name":j["name"],
                "authored_soft_swing":j["soft_swing"],"authored_soft_twist":j["soft_twist"],
                "solver_contract":"Current Jolt hard-limit policy, retaining original PHAT angles"})
        body_inverse=np.linalg.inv(c)
        # Use effective Jolt inertia, not unconditioned PHAT provenance.
        mass=matrix(b["mass_frame"])
        mass[:3,:3]=R.from_quat(b["jolt_inertia_rotation_xyzw"]).as_matrix()
        mass=body_inverse@mass
        ET.SubElement(node,"inertial",mass=text([b["jolt_mass_kg"]]),
            diaginertia=text(np.asarray(b["jolt_inertia_kg_cm2"])*1e-4),**placement(mass))
        ET.SubElement(node,"site",name=b["name"]+"_bone",size=".005",rgba="0 0 0 0",**placement(body_inverse))
        metadata["body_frames"][b["name"]]=body_inverse.tolist()
        for k,g in enumerate(b["shapes"]):
            transform=body_inverse@matrix(g["local"])
            kind=g["kind"]
            if kind=="sphere": size=[g["radius_cm"]*.01]
            elif kind=="capsule": size=[g["radius_cm"]*.01,g["cylinder_length_cm"]*.005]
            elif kind=="box": size=np.asarray(g["half_extent_cm"])*.01
            else: raise ValueError(f"Unsupported PHAT geometry {kind}, body {b['name']}")
            colour=".9 .4 .12 1" if not b["name"].endswith("_r") else ".1 .65 .7 1"
            ET.SubElement(node,"geom",name=b["name"]+f"_shape{k}",type=kind,size=text(size),rgba=colour,
                contype="1" if g["simulated"] else "0",conaffinity="1" if g["simulated"] else "0",**placement(transform))
        for j in joints:
            if j["parent"]==i: add_body(j["child"],node)
    add_body(root,world)
    assert len(visited)==len(bodies)
    key=ET.SubElement(xml,"keyframe")
    ET.SubElement(key,"key",name="original_reference",qpos=text(metadata["reference_qpos"]))
    ET.indent(xml)
    path=OUT/"uefn.xml"; ET.ElementTree(xml).write(path,encoding="utf-8",xml_declaration=True)
    model=mujoco.MjModel.from_xml_path(str(path)); data=mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model,data,0); mujoco.mj_forward(model,data)
    errors={}; shape_errors={}
    for i,b in enumerate(bodies):
        sid=model.site(b["name"]+"_bone").id
        pos=np.linalg.norm(data.site_xpos[sid]-reference[i][:3,3])*100
        rot=(R.from_matrix(data.site_xmat[sid].reshape(3,3)).inv()*R.from_matrix(reference[i][:3,:3])).magnitude()
        errors[b["name"]]={"position_cm":float(pos),"rotation_deg":float(np.rad2deg(rot))}
        for k,g in enumerate(b["shapes"]):
            gid=model.geom(b["name"]+f"_shape{k}").id
            expected=reference[i]@matrix(g["local"])
            shape_errors[f"{b['name']}_{k}"]=float(np.linalg.norm(data.geom_xpos[gid]-expected[:3,3])*100)
    assert max(x["position_cm"] for x in errors.values())<.003, errors
    assert max(x["rotation_deg"] for x in errors.values())<.0001, errors
    metadata.update({"xml_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"nq":model.nq,"nv":model.nv,
                     "mass_kg":float(sum(model.body_mass)),"reference_errors":errors,"shape_position_errors_cm":shape_errors})
    (OUT/"uefn.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    print(json.dumps({"bodies":len(bodies),"joints":len(joints),"nq":model.nq,"nv":model.nv,
        "mass_kg":metadata["mass_kg"],"max_reference_position_cm":max(x["position_cm"] for x in errors.values()),
        "max_reference_rotation_deg":max(x["rotation_deg"] for x in errors.values()),"training_ready":False},indent=2))
    return model,data,metadata

if __name__=="__main__": convert()
