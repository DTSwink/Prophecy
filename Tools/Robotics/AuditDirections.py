"""Fixed 16-case, five-second walking comparison; all native failures remain listed."""
import AuditTransfer as audit
import numpy as np
import os, json
ref=audit.ref
os.environ['AUDIT_FIXTURE']=str(audit.OUT/'point/fixture.exe')
os.environ['AUDIT_DLL_DIR']=str(ref.ROOT/'Saved/MimicKitTransfer/no-armature-3913/point-contact')
base={'CAND_SPHERICAL':'1','CAND_LIMIT_HZ':'32'}
results=[]
for case in range(2):
    source=np.load(ref.ROOT/f'Saved/Diagnostics/RobotLocomotion20261026/native-case{case}.npz')
    for degrees in range(0,360,45):
        angle=np.deg2rad(degrees); direction=[np.cos(angle),np.sin(angle)]
        row=dict(case=case,direction_deg=degrees)
        for label,backend,flags in [('native','mujoco',{}),('manifold','jolt',base|{'AUDIT_MANIFOLD':'1'}),('point','jolt',base)]:
            result,_=audit.trial(source['states'][420].copy(),source['phases'][420].copy(),direction,backend,150,flags)
            row[label]=result
        results.append(row); print(json.dumps(row),flush=True)
        (audit.OUT/'directions.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
def passed(r):return r['first_fall_tick'] is None and r['command_travel_cm']>100
native=[r for r in results if passed(r['native'])]
summary=dict(total=len(results),native_success=len(native),
    manifold_transfers=sum(passed(r['manifold']) for r in native),
    point_transfers=sum(passed(r['point']) for r in native),
    regressions=[dict(case=r['case'],direction=r['direction_deg']) for r in native if passed(r['manifold']) and not passed(r['point'])])
(audit.OUT/'directions-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary),flush=True)
