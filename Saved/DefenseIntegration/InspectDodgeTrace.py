from pathlib import Path
import numpy as np,json
folder=Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/dodge_unreal_reference/reference')
with np.load(folder/'trace.npz') as t:
    print([(k,t[k].shape) for k in t.files if k.startswith('frame/002')][:160])
print('manifest',json.loads((folder/'manifest.json').read_text()).keys())
