"""Read-only replay of recorded native inputs through installed checkpoint weights."""
import os
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
import sys,json
from pathlib import Path
import numpy as np
import torch
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
sys.path.insert(0,r'C:\Users\singerie\Documents\Cursor\stepper')
from training.ik import ik_core as tl, visualize
root=Path(__file__).resolve().parents[3]
rows=[json.loads(x) for x in (root/'Saved/Diagnostics/SlashContacts/nn_inputs.jsonl').read_text().splitlines()]
rows=[r for r in rows if r['actor']=='BP_ProphecyManualPoseAgent_C_1']
x=torch.tensor([r['lower_input'] for r in rows],dtype=torch.float32)
pub=np.array([r['published_lower'] for r in rows])
outputs={}
for name,filename in [('run','prophecy_lower_body_runtime.json'),('walk','prophecy_lower_body_walk_july5_runtime.json')]:
 c=json.loads((root/'Content/locomotion/NN'/filename).read_text())
 cp=torch.load(c['checkpoint_path'],map_location='cpu',weights_only=False)
 visualize.apply_simple_controller_policy(cp)
 cfg=tl.TrainConfig();visualize.apply_config_dict(cfg,cp['config'])
 clip=tl.MotionClip(Path(c['seed_clip_path']),cfg,cyclic_animation=True)
 model=visualize.load_model(cp,clip,cfg,torch.device('cpu')).eval()
 with torch.inference_mode():outputs[name]=model(x).numpy()
records=[]
for i,r in enumerate(rows):
 residual=pub[i,2]-float(x[i,2])
 pred={n:float(out[i,2]) for n,out in outputs.items()}
 name=min(pred,key=lambda n:abs(pred[n]-residual))
 records.append({'time':r['time'],'current_pelvis_z_cm':float(x[i,2])*100,'published_pelvis_z_cm':float(pub[i,2])*100,
  'published_change_cm':residual*100,'raw_prediction_cm':{n:z*100 for n,z in pred.items()},'best_policy':name,
  'postprocess_z_difference_cm':(residual-pred[name])*100,'previous_pelvis_z_cm':float(x[i,43])*100,
  'past_root_features':r['lower_input'][117:120],'future_first':r['lower_input'][120:124]})
out=root/'Saved/Diagnostics/LegFeedbackIsolation/collision_raw_replay.json'
out.write_text(json.dumps(records,indent=1))
print('frames',len(records),'max postprocess Z difference cm',max(abs(r['postprocess_z_difference_cm']) for r in records))
for r in records:
 if 1.05<r['time']<1.65 or abs(r['time']-round(r['time']))<.008: print(json.dumps(r))
