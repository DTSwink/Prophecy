"""Replay captured live inputs through the original checkpoint/training foot projection."""
import json,sys,math
from pathlib import Path
import numpy as np
import torch

torch.set_num_threads(2)
root=Path(__file__).resolve().parents[2]
directory=root/'Saved/Diagnostics/BackwardTurn'
contract=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())
sys.path.insert(0,r'C:\Users\singerie\Documents\Cursor\stepper')
from training.ik import ik_core as tl, train_simple_ae_controller as ctl, visualize
checkpoint=torch.load(contract['checkpoint_path'],map_location='cpu',weights_only=False)
visualize.apply_simple_controller_policy(checkpoint)
cfg=tl.TrainConfig()
visualize.apply_config_dict(cfg,checkpoint['config'])
cfg.device='cpu';cfg.cyclic_animation=True
clip=tl.MotionClip(Path(contract['seed_clip_path']),cfg,cyclic_animation=True)
store=ctl.SimpleClipStore([clip],cfg,torch.device('cpu'))
model=visualize.load_model(checkpoint,clip,cfg,torch.device('cpu')).eval()
scene=json.loads((directory/'scene.json').read_text())['rows']
traces=[json.loads(l) for l in (directory/'inputs.jsonl').read_text().splitlines()]
name=next(r['actor'] for r in scene if r['handle']==0)
scene=[r for r in scene if r['actor']==name]
traces=[r for r in traces if r['actor']==name and .95<r['time']<2.1]
inp=torch.tensor([r['lower_input'] for r in traces],dtype=torch.float32)
with torch.no_grad():
    raw=ctl.model_raw_output(model,inp,inp[:,:41],store)
    pred60,unprojected,pins=ctl.clean_output_vector_pair_with_pin_prob(raw,store,inp[:,:41],inp[:,41:82])
    pred4=ctl.apply_foot_roll_output_projection_with_pin_probabilities(unprojected,ctl._clean_output_vector_base(inp[:,:41],store),pins,store,integration_steps=4,height_pin_gate_enabled=False)
    heights=ctl.foot_roll_lowest_heights_from_vec(store,unprojected)
    soft=ctl.soft_foot_pin_probabilities(raw[:,41:43])

def yaw(a):
    c,s=math.cos(a),math.sin(a)
    return np.array([[c,0,-s],[0,1,0],[s,0,c]])
seed=np.array(contract['seed_root_rotation_rows'])
def world(p,t):
    roots=t['roots'];return (np.array(roots[8:11])+np.array(p)@seed@yaw(roots[11]))[[0,2,1]]*100
results=[]
for i,t in enumerate(traces):
    s=min(scene,key=lambda r:abs(r['t']-t['time']))
    row=dict(tick=s['tick'],time=t['time'],feet={})
    for j,(side,offset) in enumerate([('l',9),('r',25)]):
        ue=np.array(t['published_lower'][offset:offset+3])
        ref=pred4[i,offset:offset+3].numpy()
        rawpos=unprojected[i,offset:offset+3].numpy()
        ue_world=world(ue,t)
        row['feet'][side]=dict(soft_pin=float(soft[i,j]),resolved_pin=float(pins[i,j]),height_cm=float(heights[i,j]*100),
            native_reference_error_cm=float(np.linalg.norm(ue-ref)*100),
            four_vs_training_error_cm=float(torch.linalg.vector_norm(pred4[i,offset:offset+3]-pred60[i,offset:offset+3])*100),
            projection_cm=float(np.linalg.norm(ref-rawpos)*100),raw_world=world(rawpos,t).tolist(),projected_world=ue_world.tolist(),
            decoded_error_cm=float(np.linalg.norm(ue_world-np.array(s['future']['foot_'+side][:3]))),
            display_error_cm=float(np.linalg.norm(np.array(s['mesh']['foot_'+side][:3])-np.array(s['shown']['foot_'+side][:3]))))
    results.append(row)
report=dict(actor=name,training_iterations=ctl.FOOT_ROLL_INTEGRATION_STEPS,pin_mode=ctl.FOOT_ROLL_PIN_MODE,
    fake_gravity=ctl.FAKE_GRAVITY_ENABLED,rows=results)
(directory/'analysis.json').write_text(json.dumps(report,indent=2))
print('actor',name,'reference iterations',ctl.FOOT_ROLL_INTEGRATION_STEPS,'pin mode',ctl.FOOT_ROLL_PIN_MODE)
for row in results:
    if 78<=row['tick']<=112:
        print(row['tick'],[(s,{k:round(v,4) for k,v in f.items() if not isinstance(v,list)}) for s,f in row['feet'].items()])
