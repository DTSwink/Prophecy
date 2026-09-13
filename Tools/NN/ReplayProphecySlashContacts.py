"""Independently replay actual UE hook inputs through the accepted source transition."""
import json,sys
import numpy as np
from ExportProphecySlashPolicy import PROJECT,prepare,torch
torch.set_num_threads(2)
folder=PROJECT/'Saved/Diagnostics/SlashContacts'
steps=[json.loads(x) for x in (folder/sys.argv[1]).read_text().splitlines()]
# Sample across the full capture, including both clamp phases and attack boundaries.
steps=steps[::4]
batch=16
rt,model,_,_=prepare(batch)
actual=[];oracle=[]
with rt.policy_context(),torch.inference_mode():
    for start in range(0,len(steps),batch):
        rows=steps[start:start+batch]; n=len(rows)
        inputs=np.array([s['input'] for s in rows]+[rows[-1]['input']]*(batch-n),dtype=np.float32)
        oracle.extend(model(torch.from_numpy(inputs)).cpu().numpy()[:n])
        actual.extend(s['output'] for s in rows)
a=np.array(actual);b=np.array(oracle)
result={'transitions':len(a),'max_position_mm':float(np.linalg.norm((a[:,131:206]-b[:,131:206]).reshape(-1,25,3),axis=-1).max()*1000),'matrix_max':float(abs(a[:,206:431]-b[:,206:431]).max()),'pin_max':float(abs(a[:,435:437]-b[:,435:437]).max()),'latches_match':bool(np.array_equal(a[:,431:433],b[:,431:433]))}
(folder/'LiveSourceReplay.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
