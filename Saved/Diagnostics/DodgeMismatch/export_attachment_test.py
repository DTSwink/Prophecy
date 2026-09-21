import json,sys
from pathlib import Path
import numpy as np
import torch
root=Path(__file__).resolve().parents[3]
train=Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2')
sys.path[:0]=[str(train/'ParryAndDodge'),str(train)]
from dodge_banked_inputs import euler_axes
fixture=torch.load(train/'saved_defense_checkpoints/dodge_unreal_reference/overR_idle_faceoff_60cm/fixture.pt',map_location='cpu',weights_only=False)
data=json.loads((Path(__file__).parent/'viewer_hookL_82cm.json').read_text())['attacker']
p=np.asarray(data['positions'],np.float32);r=np.asarray(data['basis'],np.float32);cases=[]
for i,name in enumerate(['head','lowerarm_l','lowerarm_r','calf_l','calf_r','hand_r']):
 spec=fixture['prototype']['collider_catalog']['limbs'][name];bone=data['names'].index(spec['bone'])
 centers=p[:,bone]+np.asarray(spec['translation'],np.float32)/100@r[:,bone]
 axes=euler_axes(spec['rotation']).astype(np.float32)@r[:,bone];axes/=np.linalg.norm(axes,axis=-1,keepdims=True)
 half=np.asarray(spec['size'],np.float32)/200*1.5
 if name=='hand_r':half[np.arange(3)!=np.argmax(spec['size'])]*=2
 for frame in range(len(p)):
  cases.append(dict(index=i,bone=spec['bone'],position=p[frame,bone].tolist(),rotation=r[frame,bone].flatten().tolist(),
   center=centers[frame].tolist(),axes=axes[frame].flatten().tolist(),half=half.tolist()))
(Path(__file__).parent/'attacker_attachment_reference.json').write_text(json.dumps(dict(cases=cases)))
print('Exported',len(cases),'attachment samples directly from training catalog and viewer bone poses.')
