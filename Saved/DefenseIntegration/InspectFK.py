from pathlib import Path
import numpy as np,json
root=Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints')
for kind,directory in [('parry','parry_unreal_reference_770015'),('dodge','dodge_unreal_reference/reference')]:
    folder=root/directory
    d=json.loads((folder/'skeleton.json').read_text())
    print(kind,'configuration',[(k,v) for k,v in d.items() if k!='geometry'])
    print('geometry',[(k,np.asarray(v).shape) for k,v in d['geometry'].items()])
    with np.load(folder/'trace.npz') as t:
        print('keys',[(k,t[k].shape) for k in t.files if any(w in k for w in ('fk','baseline','decode','globals'))][:100])
