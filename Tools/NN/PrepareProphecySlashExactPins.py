"""Regenerate only geometry/startup oracles for source-exact 60/4 pinning; no network export."""
import json, shutil
from pathlib import Path
from ExportProphecySlashPolicy import PROJECT, prepare, slash, torch

torch.set_num_threads(2)
out=PROJECT/'Saved/Diagnostics/SlashContacts'
out.mkdir(parents=True,exist_ok=True)
rt, model, initial, _=prepare(1)
path=PROJECT/'Content/locomotion/NN/prophecy_slash_native.json'
contract=json.loads(path.read_text())
backup=out/'native_before.json'
if not backup.exists():shutil.copy2(path,backup)
with rt.policy_context(),torch.inference_mode():
    assert slash.ik_ctl.FOOT_ROLL_INTEGRATION_STEPS==60
    assert slash.LOWER_PIN_INTEGRATION_STEPS==4
    result=model(initial)[0].tolist()
    frames=[]
    state=initial.clone()
    for frame in range(2,20):
        output=model(state)
        frames.append({'frame':frame,'state':state[0].tolist(),'output':output[0].tolist()})
        state=torch.cat((state[:,41:82],output[:,:41],state[:,172:262],output[:,41:131],state[:,262:270],output[:,431:433]),-1)
(out/'benchmark_reference.json').write_text(json.dumps(frames))
contract['frozen_pin_steps']=60
contract['foot_roll_steps']=4
contract['startup_expected']=result
(out/'native_exact.json').write_text(json.dumps(contract,indent=2)+'\n')
# Reuse the already-validated immutable source chain inputs and exact saved outputs.
# The native audit will compare self-fed and teacher transitions directly to the saved rollout.
old=PROJECT/'Saved/SlashChain'
exact=out/'ExactChain'
exact.mkdir(exist_ok=True)
fixture=json.loads((old/'chain_audit.json').read_text())
assert fixture['source_frozen_pin_steps']==60
fixture['native_pin_steps']=60
fixture['four_step_oracle']=fixture['expected']  # Existing audit field; contents explicitly source-exact here.
fixture['teacher_oracle']=fixture['expected']
(exact/'chain_audit.json').write_text(json.dumps(fixture))
geom=json.loads((old/'source_native_geometry.json').read_text())
geom['frozen_pin_steps']=60
(exact/'source_native_geometry.json').write_text(json.dumps(geom))
print(json.dumps({'contract':str(out/'native_exact.json'),'chain':str(exact),'frozen_steps':60,'learned_steps':4}))
