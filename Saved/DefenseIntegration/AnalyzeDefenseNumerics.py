"""Read-only separation of recurrent-input drift from CPU kernel differences."""
from pathlib import Path
import json
import numpy as np
import torch
from torch import nn

torch.set_num_threads(1)
torch.set_num_interop_threads(1)
folder=Path(__file__).resolve().parent/'Models'
source=Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/dodge_unreal_reference/reference')
rows=json.loads((folder/'unreal_dodge_causal_diagnostics.json').read_text())
by_stage={r['stage']:r for r in rows}
weights=np.load(source/'weights.npz')
results=[]
for kind,width,out,prefix,final in [('lower',152,43,'frozen.models.run.net','frozen.models.run.net.6'),('upper',362,112,'upper.trunk','upper.delta_head')]:
    model=nn.Sequential(nn.Linear(width,512),nn.LayerNorm(512,eps=1e-5),nn.GELU(approximate='none'),
                        nn.Linear(512,512),nn.LayerNorm(512,eps=1e-5),nn.GELU(approximate='none'),nn.Linear(512,out)).eval()
    state={}
    for key in model.state_dict():
        index,suffix=key.split('.',1)
        state[key]=torch.from_numpy(weights[(final if index=='6' else prefix+'.'+index)+'.'+suffix].copy())
    model.load_state_dict(state)
    for row in rows:
        if not row['stage'].endswith(' '+kind+' input'):continue
        name=row['stage'][:-len(' input')]
        network=by_stage[name+' network']
        with torch.inference_mode():
            actual=model(torch.tensor([row['actual']],dtype=torch.float32)).numpy()[0]
            expected=model(torch.tensor([row['expected']],dtype=torch.float32)).numpy()[0]
        results.append({'stage':name,'input_max_error':row['max_abs'],
            'torch_vs_ort_on_actual_input':float(np.max(np.abs(actual-np.asarray(network['actual'],np.float32)))),
            'torch_vs_reference_on_reference_input':float(np.max(np.abs(expected-np.asarray(network['expected'],np.float32)))),
            'torch_output_history_drift':float(np.max(np.abs(actual-expected)))})
result={'reference_backend':json.loads((source/'manifest.json').read_text())['backend'],
        'models':results,'failures':[{k:r[k] for k in ('stage','max_abs','first_mismatch')} for r in rows if r['first_mismatch']>=0]}
(folder/'dodge_numerical_analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
