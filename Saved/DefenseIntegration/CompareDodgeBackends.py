"""Run the exact staged geometry with Torch versus ORT neural kernels.

Diagnostic only: never writes to the reference, training files or model assets.
"""
from pathlib import Path
import sys,json,types
import numpy as np
import torch

base=Path(__file__).resolve().parent
project=base.parents[1]
sys.path.insert(0,str(project/'Saved/SlashPythonDependencies'))
sys.path.insert(0,str(base/'ReferenceSources/dodge/training/slashes2/ParryAndDodge'))
import onnxruntime as ort
from build_ue5_dodge_reference import build_runtime,load_policy,native
from functools import partial

torch.set_num_threads(1);torch.set_num_interop_threads(1)
reference=Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/dodge_unreal_reference/reference')
fixture=torch.load(reference/'fixture.pt',map_location='cpu',weights_only=False)
cp=torch.load(reference/'policy.pt',map_location='cpu',weights_only=False)
work=base/'BackendDiagnostic';work.mkdir(exist_ok=True)
# The archived Python sources omit the external collider JSON, but the saved
# skeleton embeds that exact catalog. Supply it without editing the snapshot.
catalog=work/'colliders.json'
catalog.write_text(json.dumps(json.loads((reference/'skeleton.json').read_text())['collider_catalog']))
native.load_collider_geometry=partial(native.load_collider_geometry,path=catalog)
sk,episode=build_runtime(fixture,work,'cpu')
gold=np.load(reference/'trace.npz')
native={r['stage']:r for r in json.loads((base/'Models/unreal_dodge_causal_diagnostics.json').read_text())}
report={}
for backend in ('torch','ort','native_outputs'):
    agent=load_policy(cp,sk,[fixture['category']],[fixture['entry']['record']['scene']['attack']],'cpu')
    arrays={};frame=[2]
    for kind,model in [('run',agent.frozen.models['run']),('walk',agent.frozen.models['walk']),('upper',agent.upper)]:
        if backend=='ort':
            options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
            session=ort.InferenceSession(str(base/'Models'/f'prophecy_dodge_{kind}.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
            def forward(self,x,session=session,kind=kind):
                value=torch.from_numpy(session.run(None,{session.get_inputs()[0].name:x.detach().numpy()})[0])
                return (value,None) if kind=='upper' else value
            model.forward=types.MethodType(forward,model)
        elif backend=='native_outputs' and kind in ('run','upper'):
            def forward(self,x,kind=kind):
                stage=f'frame/{frame[0]:03d}/upper/output/0 '+('upper network' if kind=='upper' else 'lower network')
                value=torch.tensor(native[stage]['actual'],dtype=torch.float32).reshape(1,-1)
                return (value,None) if kind=='upper' else value
            model.forward=types.MethodType(forward,model)
        def capture(module,args,out,kind=kind):
            prefix=f'frame/{frame[0]:03d}/{kind}'
            arrays[prefix+'/input/0']=args[0].detach().numpy().copy()
            arrays[prefix+('/output/0' if kind=='upper' else '/output')]=(out[0] if kind=='upper' else out).detach().numpy().copy()
        model.register_forward_hook(capture)
    state=agent.initial_state(episode.lower_primers,episode.upper_primers,episode.root_primers)
    with torch.inference_mode():
        for f in range(2,int(episode.valid[0].sum())):
            frame[0]=f
            proposal=agent(state,episode.pelvis[:,f-1],episode.pelvis[:,f],episode.collider[:,f-1],episode.collider[:,f],episode.event[:,f],episode.target_world,episode.attack_type)
            state=proposal.state
            arrays[f'frame/{f:03d}/proposal/positions']=proposal.positions.numpy().copy()
            arrays[f'frame/{f:03d}/proposal/rotations']=proposal.rotations.numpy().copy()
            for name in ('current_lower','current_upper'):
                arrays[f'frame/{f:03d}/proposal/state/{name}']=getattr(state,name).numpy().copy()
    comparisons=[]
    for key,value in arrays.items():
        expected=gold[key];delta=np.abs(value.astype(np.float64)-expected.astype(np.float64))
        entry=dict(key=key,max_abs=float(delta.max()),passes=bool(np.allclose(value,expected,atol=1e-5,rtol=1e-5)))
        if '/run/input/' in key:
            f=key.split('/')[1];cpp=native[f'frame/{f}/upper/output/0 lower input']['actual']
            entry['cpp_vs_this_input_max_abs']=float(np.max(np.abs(value.reshape(-1)-np.asarray(cpp,np.float32))))
        comparisons.append(entry)
    report_key={'positions':'positions','rotations':'rotations','state/current_lower':'recurrent lower','state/current_upper':'recurrent upper'}
    for key,value in arrays.items():
        suffix=key.split('/proposal/')[-1]
        if suffix in report_key:
            stage=f'frame/{key.split("/")[1]}/upper/output/0 '+report_key[suffix]
            delta=np.abs(value.reshape(-1)-np.asarray(native[stage]['actual'],np.float32))
            comparisons.append(dict(key=key+' vs native',max_abs=float(delta.max()),passes=bool(np.all(delta<=1e-5))))
    report[backend]=comparisons
    np.savez(work/f'{backend}_trace.npz',**arrays)
(work/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:dict(max_abs=max(r['max_abs'] for r in rows),failed=[r for r in rows if not r['passes']]) for k,rows in report.items()},indent=2))
