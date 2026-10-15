"""Exercise the actual isolated worker protocol used by Stepper."""
import argparse
import json
import sys
import time
from pathlib import Path
import numpy as np
sys.path.insert(0,"C:/Users/singerie/Documents/Cursor/stepper/training")
from physical_checkpoint_viewer import Client

OUT=Path(__file__).resolve().parents[2]/"Saved/Robotics"

def wait(client):
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        client.poll()
        if client.error:raise RuntimeError(client.error)
        if client.ready and not client.pending:return client.latest
        time.sleep(.02)
    raise TimeoutError("Physical worker response timeout")

def main():
    p=argparse.ArgumentParser();p.add_argument("checkpoint");a=p.parse_args()
    client=Client(a.checkpoint)
    try:
        initial=wait(client);assert len(initial["shapes"])==23
        for name in ("foot_l","foot_r"):
            shape=next(s for s in initial["shapes"] if s["bone"]==name)
            np.testing.assert_allclose(shape["dimensions"],[.09,.27,.115])
        client.send({"op":"step","ticks":4});first=wait(client);assert first["tick"]==4
        origin=(np.array(first["positions"][0])+[0,1.0,-3.]).tolist()
        client.send({"op":"launch","origin":origin});launched=wait(client);assert len(launched["shapes"])==24
        cube_start=np.array(launched["centers"][-1]);minimum_distance=100.
        for _ in range(30):
            client.send({"op":"step","ticks":2});d=wait(client)
            assert np.isfinite(d["positions"]).all() and np.isfinite(d["centers"]).all()
            minimum_distance=min(minimum_distance,np.min(np.linalg.norm(np.array(d["positions"])-np.array(d["centers"][-1]),axis=1)))
        cube_motion=float(np.linalg.norm(np.array(d["centers"][-1])-cube_start))
        assert cube_motion>1 and minimum_distance<.5,(cube_motion,minimum_distance)
        contact_impulse=float(sum(d['cube_rig_contact_impulse_ns']))
        assert contact_impulse>0, 'Cube proximity without any measured cube-rig contact'
        client.send({"op":"reset"});reset=wait(client);assert reset["tick"]==0 and len(reset["shapes"])==23
        np.testing.assert_allclose(reset["positions"],initial["positions"],atol=1e-6)
        assert sum(reset['cube_rig_contact_impulse_ns'])==0
        report={"passed":True,"feet_dimensions_m":[.09,.27,.115],"cube_mass_kg":30,"cube_dimensions_m":[.45]*3,
            "cube_displacement_m":cube_motion,"minimum_cube_to_bone_distance_m":float(minimum_distance),"reset_exact":True,
            'measured_cube_rig_normal_impulse_ns':contact_impulse}
        (OUT/"physical-runtime-test.json").write_text(json.dumps(report,indent=2),encoding="utf-8");print(json.dumps(report,indent=2))
    finally:client.close()

if __name__=="__main__":main()
