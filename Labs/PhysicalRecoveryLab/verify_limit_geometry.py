"""Compare every exported joint's admissible rotations against actual Jolt code."""
from pathlib import Path
import json
import os
import subprocess
import numpy as np
from scipy.spatial.transform import Rotation as R
from test_phat_constraints import reference

ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/"Saved/Robotics"

def main():
    meta=json.loads((OUT/"uefn.json").read_text())
    rng=np.random.default_rng(93); rows=[]
    for j in meta["joints"]:
        a=np.array(j["limits_rad"]); modes=np.array(j["modes"])
        for i in range(400):
            # Wide actual rotation space, including coupled swing and quaternion sign changes.
            q=R.from_rotvec(rng.normal(size=3)*rng.uniform(.001,1.4)).as_quat()[[3,0,1,2]]
            if i%2: q=-q
            rows.append(np.r_[len(rows),modes,a,q])
    values=np.asarray(rows)
    src=OUT/"limit-geometry-input.csv"; dst=OUT/"limit-geometry-jolt.csv"
    np.savetxt(src,values,delimiter=",",fmt=["%d"]*4+["%.12g"]*7,header="index,m0,m1,m2,a,b,c,w,x,y,z",comments="")
    env=os.environ.copy(); env["PATH"]=str(ROOT/"Intermediate/JoltMigration/Install/Development/bin")+os.pathsep+env["PATH"]
    subprocess.run([str(OUT/"jolt_probe.exe"),"--limits",str(src),str(dst)],env=env,check=True)
    result=np.genfromtxt(dst,delimiter=",",names=True)
    actual=np.column_stack([result[n] for n in ("twist","swing_y","swing_z")])
    predicted=reference(values[:,7:11])
    error=np.max(np.abs(actual-predicted),axis=0)
    assert error.max()<2e-5,error
    mismatches=[]
    for i,(r,v) in enumerate(zip(values,predicted)):
        modes=r[1:4].astype(int); limits=r[4:7]
        violation=abs(v[0])>limits[0]+2e-6 if modes[0]==1 else modes[0]==2 and abs(v[0])>2e-6
        if modes[1]==modes[2]==1:
            violation|=(v[1]/np.sin(limits[1]/2))**2+(v[2]/np.sin(limits[2]/2))**2>1+2e-6
        else:
            for axis in (1,2):
                violation|=abs(v[axis])>(np.sin(limits[axis]/2) if modes[axis]==1 else 0)+2e-6 if modes[axis]!=0 else False
        # All randomly sampled locked-axis errors are well above rounding noise.
        if bool(result["mask"][i])!=bool(violation): mismatches.append(i)
    assert not mismatches,mismatches[:20]
    report={"samples":len(rows),"joint_profiles":len(meta["joints"]),"jolt_version":"project 5.6 DLL",
        "coordinate_max_errors":error.tolist(),"admissibility_mismatches":mismatches,"passed":True,
        "scope":"Limit geometry only. This does not establish equal solver impulse response."}
    from provenance import verify_export
    report.update(verify_export())
    (OUT/"limit-geometry.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
