import json,torch,numpy as np
from pathlib import Path
root=Path(__file__).resolve().parents[3]
source=Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints/dodge_unreal_reference')
fixture=torch.load(source/'overR_idle_faceoff_60cm/fixture.pt',map_location='cpu',weights_only=False)
native=json.loads((root/'Content/locomotion/NN/defense/dodge_skeleton.json').read_text())['geometry']
report={}
for key,v in fixture['geometry'].items():
 if key not in native:continue
 a=v.numpy();b=np.asarray(native[key]);error=float(np.max(np.abs(a.reshape(-1)-b.reshape(-1))))
 if error>1e-7:report[key]=error
print('Different reference geometry',report)
