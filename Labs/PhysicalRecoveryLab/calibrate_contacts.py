"""Compare primitive traces with the project's actual Jolt DLL.

This measures response, not an assertion that the two contact solvers are identical.
"""
from pathlib import Path
import json
import numpy as np
import mujoco
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"Saved/Robotics"

def trace(test,dt,friction,solref,solimp):
    box=test.startswith("box")
    slide=test=="box_slide"
    shape='type="box" size=".1 .1 .1"' if box else 'type="sphere" size=".1"'
    xml=f'''<mujoco><option timestep="{dt:.12g}" gravity="0 0 -9.81" integrator="implicitfast"
    cone="elliptic" iterations="50" tolerance="1e-10"/>
    <default><geom friction="{friction} 0 0" condim="3" solref="{solref}" solimp="{solimp}"/></default>
    <worldbody><geom type="plane" size="10 10 .1"/>
    <body pos="0 0 {'.1' if slide else '1'}"><freejoint/><geom {shape} mass="1"/></body></worldbody></mujoco>'''
    model=mujoco.MjModel.from_xml_string(xml)
    data=mujoco.MjData(model)
    if slide: data.qvel[0]=2
    rows=[]
    for tick in range(round(2/dt)+1):
        rows.append(np.r_[tick*dt,data.qpos[:3],data.qvel[:3]])
        mujoco.mj_step(model,data)
    return np.asarray(rows)

def main():
    jolt=np.genfromtxt(OUT/"jolt-calibration.csv",delimiter=",",names=True,dtype=None,encoding="utf-8")
    options=[("default",".02 1",".9 .95 .001 .5 2"),
             ("stiff",".0083333333 1",".95 .99 .001 .5 2"),
             ("stiff_high_impedance",".0083333333 1",".99 .999 .001 .5 2")]
    reports=[]; traces={}
    for label,solref,solimp in options:
        for dt in sorted(set(jolt["dt"])):
            for mu in sorted(set(jolt["friction"])):
                for test in ("sphere_drop","box_drop","box_slide"):
                    ref=jolt[(jolt["test"]==test)&(jolt["dt"]==dt)&(jolt["friction"]==mu)]
                    pred=trace(test,dt,mu,solref,solimp)
                    actual=np.column_stack([ref[n] for n in ("x","y","z")])
                    delta=pred[:,1:4]-actual
                    result={"profile":label,"dt":dt,"friction":mu,"test":test,
                            "position_rmse_cm":float(np.sqrt(np.mean(np.sum(delta**2,axis=1)))*100),
                            "position_peak_cm":float(np.max(np.linalg.norm(delta,axis=1))*100),
                            "end_position_delta_cm":(delta[-1]*100).tolist(),
                            "jolt_end_m":actual[-1].tolist(),"mujoco_end_m":pred[-1,1:4].tolist()}
                    reports.append(result)
                    if abs(dt-1/240)<1e-7 and abs(mu-.7)<1e-6:
                        traces[(label,test)]=(ref,pred)
    scores={label:float(np.mean([r["position_rmse_cm"] for r in reports
             if r["profile"]==label and abs(r["dt"]-1/240)<1e-7])) for label,_,_ in options}
    best=min(scores,key=scores.get)
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,test in zip(axes,("sphere_drop","box_drop","box_slide")):
        column="x" if test=="box_slide" else "z"
        index=1 if column=="x" else 3
        ref,pred=traces[(best,test)]
        ax.plot(ref["time"],ref[column]*100,label="Jolt (project DLL)")
        ax.plot(pred[:,0],pred[:,index]*100,label="MuJoCo",linestyle="--")
        ax.set(title=test,xlabel="Seconds",ylabel=f"{column.upper()} · cm")
        ax.grid(alpha=.3)
    axes[0].legend(); fig.suptitle(f"Primitive calibration · 240 Hz · friction 0.7 · {best}")
    fig.tight_layout(); fig.savefig(OUT/"contact-calibration.png",dpi=140); plt.close(fig)
    summary={"scope":"Primitive tests only; no humanoid transfer established.",
             "jolt":"project pinned 5.6 DLL", "mujoco":mujoco.__version__,
             "scores_at_240_hz_mean_rmse_cm":scores,"best_tested_profile":best,
             "profiles":options,"cases":reports}
    (OUT/"contact-calibration.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!="cases"},indent=2))

if __name__=="__main__": main()
