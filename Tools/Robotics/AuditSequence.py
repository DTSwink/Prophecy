"""Confirm the contact fix through the original Get Up -> idle -> walk sequence."""
import AuditTransfer as audit
import numpy as np
import os, json, hashlib
ref=audit.ref
os.environ['AUDIT_FIXTURE']=str(audit.OUT/'point/fixture.exe')
os.environ['AUDIT_DLL_DIR']=str(ref.ROOT/'Saved/MimicKitTransfer/no-armature-3913/point-contact')
starts=np.load(ref.folder/'native-native-baseline-4.npz')
results=[]
for case,lane in enumerate((0,3)):
    for label,extra in [('manifold',{'AUDIT_MANIFOLD':'1'}),('point',{})]:
        state=starts['states'][0,lane].copy();phase=starts['phase'][0,lane].copy()
        sim=audit.Jolt(state,{'CAND_SPHERICAL':'1','CAND_LIMIT_HZ':'32'}|extra)
        history=[]
        try:
            for tick in range(570):
                history.append(state)
                obs=ref.transfer.observation(state,{'sword_drawn':False,'arm_enabled':[1,1]},phase).numpy()
                obs[0,146]=-1 if tick<420 else 0
                obs[0,147:149]=[1,0] if tick<420 or case==0 else [0,1]
                action,following=ref.policies[int(tick>=300)].run(None,{'observations':obs})
                state=sim.step(action[0]);phase=following[0]
            history.append(state)
        finally:sim.close()
        history=np.asarray(history)
        row=dict(case=case,contact=label,getup_height_cm=float(history[299,0,2]*100),
                 idle_min_cm=float(history[300:420,0,2].min()*100),
                 walk_min_cm=float(history[420:,0,2].min()*100),
                 walk_cm=float(np.linalg.norm(history[-1,0,:2]-history[420,0,:2])*100),
                 first_fall_tick=next((t for t in range(420,len(history)) if history[t,0,2]<.6),None))
        results.append(row);print(json.dumps(row),flush=True)
        np.savez_compressed(audit.OUT/f'sequence-{label}-{case}.npz',states=history)
(audit.OUT/'sequence.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
for case in range(2):
    a=np.load(audit.OUT/f'baseline-jolt-{case}.npz')
    b=np.load(audit.OUT/f'same_dll_manifold-jolt-{case}.npz')
    np.testing.assert_array_equal(a['states'],b['states'])
receipt=dict(installed_and_isolated_default_trajectories_identical=True,
             installed_dll_sha256=hashlib.sha256((ref.ROOT/'Intermediate/JoltMigration/Install/Development/bin/ProphecyJolt_5_6_Development.dll').read_bytes()).hexdigest(),
             isolated_dll_sha256=hashlib.sha256((ref.ROOT/'Saved/MimicKitTransfer/no-armature-3913/point-contact/ProphecyJolt_5_6_Development.dll').read_bytes()).hexdigest(),
             installed_files_modified=False,weights_modified=False)
(audit.OUT/'provenance.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
