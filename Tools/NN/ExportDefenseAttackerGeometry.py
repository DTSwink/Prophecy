"""Export attacker conditioning separately from defender collision geometry."""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
import torch

PROJECT=Path(__file__).resolve().parents[2]
TRAINING=Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2')
sys.path[:0]=[str(TRAINING/'ParryAndDodge'),str(TRAINING)]
from dodge_banked_inputs import euler_axes

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--viewer-rollout',type=Path,help='Optional independent viewer JSON for the native attachment regression.')
    args=parser.parse_args()
    source=TRAINING/'saved_defense_checkpoints/dodge_unreal_reference/overR_idle_faceoff_60cm/fixture.pt'
    fixture=torch.load(source,map_location='cpu',weights_only=False)
    catalog=fixture['prototype']['collider_catalog']['limbs']
    parry=json.loads((TRAINING/'saved_defense_checkpoints/parry_unreal_reference_770015/collider_catalog.json').read_text())['limbs']
    names=json.loads((PROJECT/'Content/locomotion/NN/defense/dodge_skeleton.json').read_text())['joint_names']
    records=[]
    for name in ['head','lowerarm_l','lowerarm_r','calf_l','calf_r','hand_r']:
        spec=catalog[name]
        for field in ['bone','translation','rotation','size']:
            assert spec[field]==parry[name][field],(name,field,'Parry/Dodge attacker catalogs differ')
        axes=euler_axes(spec['rotation']).astype(np.float32)
        offset=np.asarray(spec['translation'],np.float32)/100
        half=np.asarray(spec['size'],np.float32)/200*1.5
        if name=='hand_r':half[np.arange(3)!=int(np.argmax(spec['size']))]*=2
        records.append(dict(name='blade' if name=='hand_r' else name,bone=names.index(spec['bone']),
            offset=offset.tolist(),axes=axes.flatten().tolist(),half=half.tolist(),center_offset=[0,0,0]))
    doc=dict(version=1,base_count=6,source_fixture_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        rule='Raw attacker bone attachment; size multiplier 1.5; blade transverse size multiplier 2. No defender forearm reconstruction/thinning.',colliders=records)
    path=PROJECT/'Content/locomotion/NN/defense/attacker_colliders.json'
    path.write_text(json.dumps(doc,indent=2)+'\n')
    print(path)
    if args.viewer_rollout:
        data=json.loads(args.viewer_rollout.read_text())['attacker'];cases=[]
        p=np.asarray(data['positions'],np.float32);r=np.asarray(data['basis'],np.float32)
        for i,name in enumerate(['head','lowerarm_l','lowerarm_r','calf_l','calf_r','hand_r']):
            spec=catalog[name];bone=data['names'].index(spec['bone'])
            centers=p[:,bone]+(np.asarray(spec['translation'],np.float32)/100)@r[:,bone]
            axes=euler_axes(spec['rotation']).astype(np.float32)@r[:,bone]
            axes/=np.linalg.norm(axes,axis=-1,keepdims=True)
            half=np.asarray(spec['size'],np.float32)/200*1.5
            if name=='hand_r':half[np.arange(3)!=np.argmax(spec['size'])]*=2
            for frame in range(len(p)):
                cases.append(dict(index=i,bone=spec['bone'],position=p[frame,bone].tolist(),rotation=r[frame,bone].flatten().tolist(),
                    center=centers[frame].tolist(),axes=axes[frame].flatten().tolist(),half=half.tolist()))
        target=PROJECT/'Saved/Diagnostics/DodgeMismatch/attacker_attachment_reference.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(dict(cases=cases)))
        print(f'Exported {len(cases)} reference attachment samples.')

if __name__=='__main__':main()
