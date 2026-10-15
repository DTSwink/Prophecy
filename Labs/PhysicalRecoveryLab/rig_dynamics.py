"""mjlab GPU rig smoke, bounded-contact telemetry and settled-pose generation."""
from pathlib import Path
import argparse
import json
import time
import numpy as np
from scipy.spatial.transform import Rotation as R
import mujoco
import warp as wp
import torch
import xml.etree.ElementTree as ET
from mjlab.sim import Simulation,SimulationCfg,MujocoCfg
from phat_constraints import PhatConstraints

OUT=Path(__file__).resolve().parents[2]/"Saved/Robotics"

def build(num_envs=16,cube_count=0,jacobian="auto",integrator="euler",native_motors=False,solver="newton",contact_capacity=256,constraint_capacity=768,ccd_iterations=50,gyroscopic_forces=True):
    from provenance import verify_export
    verify_export()
    # Tensor actions/observations and Warp graphs share one CUDA stream.
    torch_stream=torch.cuda.Stream()
    torch_stream.wait_stream(torch.cuda.current_stream())
    torch.cuda.set_stream(torch_stream)
    warp_stream=wp.stream_from_torch(torch_stream)
    wp.set_stream(warp_stream)
    metadata=json.loads((OUT/"uefn.json").read_text())
    if cube_count or native_motors:
        tree=ET.parse(OUT/"uefn.xml");root=tree.getroot();world=root.find("worldbody")
        extra=[]
        for i in range(cube_count):
            pos=[100.+i,100.,.225]
            body=ET.SubElement(world,"body",name=f"impact_cube_{i}",pos=" ".join(map(str,pos)))
            ET.SubElement(body,"freejoint",name=f"impact_cube_{i}_joint")
            ET.SubElement(body,"geom",name=f"impact_cube_{i}_shape",type="box",size=".225 .225 .225",mass="30",rgba=".5 .55 .65 1")
            extra.extend(pos+[1,0,0,0])
        key=root.find("keyframe/key");key.set("qpos",key.get("qpos")+" "+" ".join(map(str,extra)))
        if native_motors:
            from joint_pd import motor_gains_for
            if integrator!='implicitfast':raise ValueError('Native motor trial requires implicitfast')
            actuators=ET.SubElement(root,'actuator')
            for j in metadata['joints']:
                _,kd,cap=motor_gains_for(j['body'])
                # Independent bounded axes; sqrt(3) guarantees the original
                # per-joint vector torque budget is never increased.
                bound=cap/np.sqrt(3)
                for axis in range(3):
                    gear=np.eye(3)[axis].tolist()+[0,0,0]
                    ET.SubElement(actuators,'general',name=j['name']+f'_motor{axis}',joint=j['name'],
                        gear=' '.join(map(str,gear)),gainprm='1',biastype='affine',biasprm=f'0 0 {-kd}',
                        forcelimited='true',forcerange=f'{-bound} {bound}')
        model=mujoco.MjModel.from_xml_string(ET.tostring(root,encoding="unicode"))
    else:
        model=mujoco.MjModel.from_xml_path(str(OUT/"uefn.xml"))
    disableflags=("filterparent",)
    if integrator=="euler":
        # PD and body damping are explicit external forces in both paths. There
        # are no native velocity derivatives for implicitfast to integrate.
        if model.nu or model.ntendon or np.any(model.dof_damping) or model.opt.viscosity or model.opt.density:
            raise ValueError("Euler optimization requires zero native velocity-dependent forces")
        disableflags+=("eulerdamp",)
    cfg=SimulationCfg(nconmax=contact_capacity,njmax=constraint_capacity,ls_parallel=True,
        mujoco=MujocoCfg(timestep=1/240,integrator=integrator,cone="elliptic",iterations=50,jacobian=jacobian,solver=solver,ccd_iterations=ccd_iterations,
                        ls_iterations=20,disableflags=disableflags))
    sim=Simulation(num_envs,cfg,model,"cuda:0")
    # Both owners must outlive the captured graphs; a temporary bridge unregisters the stream.
    sim.physical_torch_stream=torch_stream
    sim.physical_warp_stream=warp_stream
    sim.native_motors=native_motors
    sim.gyroscopic_forces=gyroscopic_forces
    if native_motors:
        from motor_derivative import DiagonalMotorDerivative
        DiagonalMotorDerivative(model,sim.wp_model)
    PhatConstraints(model,sim.wp_model,metadata)
    # The initial graphs predate registration; capture again with the extra rows.
    sim.create_graph()
    return sim,metadata

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--worlds",type=int,default=16)
    parser.add_argument("--seconds",type=float,default=8)
    args=parser.parse_args()
    wp.init(); start=time.perf_counter()
    sim,meta=build(args.worlds)
    warmup=time.perf_counter()-start
    q=np.tile(np.array(meta["reference_qpos"],dtype=np.float32),(args.worlds,1))
    for i in range(args.worlds):
        # Fixed prone/supine/side fixtures, then seeded rotations. All joints start at the exported pose.
        rotation=R.from_euler("x",[90,-90,0,180][i%4],degrees=True)
        q[i,3:7]=(rotation*R.from_quat(q[i,[4,5,6,3]])).as_quat()[[3,0,1,2]]
        q[i,2]=.7
    with wp.ScopedDevice("cuda:0"):
        wp.copy(sim.wp_data.qpos,wp.array(q,dtype=float)); sim.wp_data.qvel.zero_()
        wp.capture_launch(sim.forward_graph)
        snapshots=[]; counts=[]; steps=round(args.seconds*240)
        begin=time.perf_counter()
        for step in range(steps):
            wp.capture_launch(sim.step_graph)
            if step%120==0 or step==steps-1:
                state=sim.wp_data.qpos.numpy(); velocity=sim.wp_data.qvel.numpy()
                assert np.isfinite(state).all() and np.isfinite(velocity).all(),step
                nconstraints=sim.wp_data.nefc.numpy(); contacts=sim.wp_data.nacon.numpy()
                if nconstraints.max()>=sim.wp_data.njmax: raise RuntimeError(f"Constraint overflow {nconstraints.max()}")
                if contacts[0]>=sim.wp_data.naconmax: raise RuntimeError(f"Contact overflow {contacts[0]}")
                snapshots.append(state.copy()); counts.append({"step":step,"max_rows":int(nconstraints.max()),"contacts":int(contacts[0]),
                    "max_abs_velocity":float(np.abs(velocity).max())})
        wp.synchronize(); elapsed=time.perf_counter()-begin
    # Preserve the measured velocities; do not label a moving pose static.
    final=sim.wp_data.qpos.numpy(); velocities=sim.wp_data.qvel.numpy()
    np.savez_compressed(OUT/"rig-passive.npz",qpos=final,qvel=velocities,samples=np.array(snapshots))
    report={"worlds":args.worlds,"steps":steps,"cuda_graph":sim.use_cuda_graph,"warmup_seconds":warmup,
        "rig_sha256":meta["rig_sha256"],"xml_sha256":meta["xml_sha256"],
        "wall_seconds_including_diagnostics":elapsed,"world_steps_per_second":steps*args.worlds/elapsed,
        "final_max_abs_velocity":float(np.abs(velocities).max()),"pelvis_z_range_m":[float(final[:,2].min()),float(final[:,2].max())],
        "counts":counts,"finite":True,"training_ready":False}
    (OUT/"rig-passive.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
