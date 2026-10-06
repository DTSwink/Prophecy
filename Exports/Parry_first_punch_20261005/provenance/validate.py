from pathlib import Path
import json,sys,importlib.util
import numpy as np
import torch
P=Path('Exports/Parry_first_punch_20261005');CODE=Path('C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/ParryAndDodge')
spec=importlib.util.spec_from_file_location('export_case',P/'load_case.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
torch.set_num_threads(1);agent,episode,meta,errors=m.load_case(CODE)
from transition_agents import State
raw=P/'reference_unreal';before=[json.loads(p.read_text()) for p in sorted(raw.glob('*_before.json'))]
before=[v for v in before if v['owner']==meta['defender'] and v['family'].lower()==meta['attack'].lower()]
ref=np.load(raw/'native_parry_arrays.npz');records=[]
def t(v):return torch.tensor(v,dtype=torch.float32)[None]
inputs=[];outputs=[]
def hook(module,x,y):inputs.append(x[0].detach());outputs.append(y[0].detach())
h=agent.upper.register_forward_hook(hook)
for i,u in enumerate(before):
 s=u['state'];pr=t(s['previous_root']);cr=t(s['current_root'])
 state=State(t(s['previous_lower']),t(s['previous_upper']),t(s['current_lower']),t(s['current_upper']),pr[:,:3],pr[:,3:].reshape(1,3,3),cr[:,:3],cr[:,3:].reshape(1,3,3),pr[:,3:].reshape(1,3,3),t(s['initial_delta_world']),t(s['initial_delta_yaw']).reshape(1,1))
 with torch.inference_mode():agent.step(state,episode,i+2)
 records.append(dict(frame=u['frame'],input_max_abs=float((inputs[-1][0]-torch.from_numpy(ref['inputs'][i])).abs().max()),output_max_abs=float((outputs[-1][0]-torch.from_numpy(ref['outputs'][i])).abs().max())))
h.remove()
assert max(v['input_max_abs'] for v in records)<5.e-5,records
assert max(v['output_max_abs'] for v in records)<5.e-5,records
smoke=np.load(P/'vanilla_parry_smoke.npz')
report={'one_step_native_boundary_checks':records,'max_input_error':max(v['input_max_abs'] for v in records),'max_output_error':max(v['output_max_abs'] for v in records),'vanilla_first_input_max_abs':float(np.max(np.abs(smoke['policy_inputs'][0]-ref['inputs'][0]))),'vanilla_all_inputs_max_abs':float(np.max(np.abs(smoke['policy_inputs']-ref['inputs']))),'initialization_max_abs':max(errors.values()),'scope':'One-step parity uses native recurrent states for verification only. load_case.py never reads these future upper states or future UE root-command overrides.'}
(P/'native_boundary_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
