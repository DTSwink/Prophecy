"""Same initial state and action: UE owner versus standalone Jolt stepping."""
import json, os
import numpy as np
import AuditTransfer as audit

os.environ['AUDIT_FIXTURE']=str(audit.OUT/'point/fixture.exe')
os.environ['AUDIT_DLL_DIR']=str(audit.ROOT/'Intermediate/JoltMigration/Install/Development/bin')
rows=json.loads((audit.ROOT/'Saved/Diagnostics/RobotLocomotion20261026/contact-trace-2.json').read_text(encoding='utf-8-sig'))
results=[]
for clanker,case in ((False,71),(True,0),(True,10)):
    selected=[r for r in rows if r['clanker']==clanker and r['case']==case]
    start=np.asarray(selected[0]['states']);start[:,:3]*=.01;start[:,7:10]*=.01
    target=np.asarray(selected[1]['states']);target[:,:3]*=.01;target[:,7:10]*=.01
    for label,flag in [('normal',{}),('grouped',{'AUDIT_GROUP_LIMITS':'1'}),('no_drag',{'TRANSFER_NO_DRAG':'1'}),
                       ('manifold',{'AUDIT_MANIFOLD':'1'}),('no_contact',{'TRANSFER_NO_CONTACT':'1'})]:
        sim=audit.Jolt(start,{'CAND_SPHERICAL':'1','CAND_LIMIT_HZ':'32'}|flag)
        try:
            actual=sim.step(selected[0]['action'])
            delta=actual-target
            item=dict(clanker=clanker,case=case,label=label,position_cm=float(abs(delta[:,:3]).max()*100),
                velocity=float(abs(delta[:,7:10]).max()),angular=float(abs(delta[:,10:13]).max()),
                per_body_angular=np.max(abs(delta[:,10:13]),axis=1).tolist())
            results.append(item);print(json.dumps(item),flush=True)
            np.savez_compressed(audit.OUT/f'trace-{clanker}-{case}-{label}.npz',actual=actual,target=target,start=start)
        finally:sim.close()
(audit.OUT/'trace-comparison.json').write_text(json.dumps(results,indent=2))
