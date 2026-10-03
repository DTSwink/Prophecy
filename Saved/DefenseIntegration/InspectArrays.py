import numpy as np,pathlib,json
root=pathlib.Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints')
for name,folder in [('dodge',root/'dodge_unreal_reference/reference'),('parry',root/'parry_unreal_reference_770015')]:
    w=np.load(folder/'weights.npz')
    print(name,'weights',[(k,w[k].shape) for k in w.files])
    t=np.load(folder/'trace.npz')
    print(name,'network traces',[(k,t[k].shape) for k in t.files if any(s in k for s in ('input','output','delta','network'))][:70])
    for filename in ['skeleton.json','inputs.json','fixture_inputs.json']:
        if (folder/filename).exists():
            d=json.loads((folder/filename).read_text());print(name,filename,list(d))
