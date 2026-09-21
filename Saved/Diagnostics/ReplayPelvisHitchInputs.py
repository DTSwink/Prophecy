"""Isolate recorded input groups without changing Unreal or checkpoint files."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import sys,json,pathlib,itertools
import numpy as np
import torch
torch.set_num_threads(1);torch.set_num_interop_threads(1)
root=pathlib.Path(__file__).resolve().parents[2]
out=root/'Saved/Diagnostics/PelvisHitchInputs';out.mkdir(exist_ok=True)
def load(name):
    rows=[json.loads(x) for x in (root/'Saved/Diagnostics'/name/'pipeline.jsonl').read_text().splitlines()]
    return {round(r['time']*60):r for r in rows if r['actor'].endswith('_C_1')}
b=load('PelvisHitch-20260920-193832');a=load('PelvisHitch-20260920-194230')
contract=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json').read_text())
sys.path.insert(0,r'C:\Users\singerie\Documents\Cursor\stepper')
from training.ik import ik_core as tl,visualize
cp=torch.load(contract['checkpoint_path'],map_location='cpu',weights_only=False)
visualize.apply_simple_controller_policy(cp)
cfg=tl.TrainConfig();visualize.apply_config_dict(cfg,cp['config'])
clip=tl.MotionClip(pathlib.Path(contract['seed_clip_path']),cfg,cyclic_animation=True)
model=visualize.load_model(cp,clip,cfg,torch.device('cpu')).eval()
def predict(x):
    with torch.inference_mode():return model(torch.tensor(np.asarray(x),dtype=torch.float32)).numpy()
ticks=[t for t in b if 151<=t<=195]
pb=predict([b[t]['lower_input'] for t in ticks]);pa=predict([a[t]['lower_input'] for t in ticks])
print('Checkpoint replay errors',np.max(abs(pb-np.array([b[t]['lower_delta'] for t in ticks]))),np.max(abs(pa-np.array([a[t]['lower_delta'] for t in ticks]))),flush=True)
groups={'left_thigh':list(range(18,24)),'right_thigh':list(range(34,40)),
        'foot_positions':list(range(9,12))+list(range(25,28)),
        'foot_rotations_toes':list(range(12,18))+[24]+list(range(28,34))+[40]}
base=np.array(b[175]['lower_input']);alt=np.array(a[175]['lower_input'])
changes=[{'index':i,'baseline':float(base[i]),'no_reconstruction':float(alt[i]),'difference':float(base[i]-alt[i])} for i in range(len(base)) if abs(base[i]-alt[i])>1e-7]
variants={'baseline':base.copy(),'all_no_reconstruction':alt.copy()}
for name,indices in groups.items():
    for mode in ('pose_only','difference_only','pose_and_difference'):
        ix=(indices if mode!='difference_only' else [])+([i+76 for i in indices] if mode!='pose_only' else [])
        v=base.copy();v[ix]=alt[ix];variants[name+'/'+mode]=v
for mask in range(1,16):
    keys=[k for i,k in enumerate(groups) if mask&(1<<i)]
    ix=[j for k in keys for i in groups[k] for j in (i,i+76)]
    v=base.copy();v[ix]=alt[ix];variants['coherent/'+'+'.join(keys)]=v
from scipy.spatial.transform import Rotation
def rot(v):
    v=np.array(v);x=v[:3]/np.linalg.norm(v[:3]);y=v[3:]-x*np.dot(x,v[3:]);y/=np.linalg.norm(y)
    return np.array([x,y,np.cross(x,y)])
solve=next(r for r in json.loads((out/'solve_replay.json').read_text()) if r['tick']==173)
for sides in [('left',),('right',),('left','right')]:
    v=base.copy()
    for side in sides:
        o=18 if side=='left' else 34
        carry=rot(b[173]['published_lower'][o:o+6]).T@rot(base[o:o+6])
        v[o:o+6]=(np.array(solve['transported'][side])@carry)[:2].ravel()
        v[o+76:o+82]=(v[o:o+6]-v[o+41:o+47])/contract['pose_delta_scale_final']
    variants['remove_only_knee_guidance/'+'+'.join(sides)]=v
ys=predict(list(variants.values()));basey=ys[0];alty=ys[1];records=[]
for (name,x),y in zip(variants.items(),ys):
    record={'name':name,'pelvis_delta_cm':(y[:3]*100).tolist(),'change_cm':((y-basey)[:3]*100).tolist(),
            'recovered_fraction':float(np.dot((y-basey)[:3],(alty-basey)[:3])/np.dot((alty-basey)[:3],(alty-basey)[:3]))}
    records.append(record)
    if not name.startswith('coherent/'):print(json.dumps(record),flush=True)
result={'checkpoint':contract['checkpoint_path'],'baseline_replay_max':float(np.max(abs(pb-np.array([b[t]['lower_delta'] for t in ticks])))),
        'ablation_replay_max':float(np.max(abs(pa-np.array([a[t]['lower_delta'] for t in ticks])))), 'changed_inputs_at_175':changes,'variants':records}
(out/'replay.json').write_text(json.dumps(result,indent=2))
print('SAVED',out/'replay.json',flush=True)
second_base=np.array(b[179]['lower_input'])
second_solve=next(r for r in json.loads((out/'solve_replay.json').read_text()) if r['tick']==177)
second_variants={'baseline':second_base.copy()}
for sides in [('left',),('right',),('left','right')]:
    v=second_base.copy()
    for side in sides:
        o=18 if side=='left' else 34
        carry=rot(b[177]['published_lower'][o:o+6]).T@rot(second_base[o:o+6])
        v[o:o+6]=(np.array(second_solve['transported'][side])@carry)[:2].ravel()
        v[o+76:o+82]=(v[o:o+6]-v[o+41:o+47])/contract['pose_delta_scale_final']
    second_variants['remove_only_knee_guidance/'+'+'.join(sides)]=v
second_y=predict(list(second_variants.values()))
second_result=[{'name':name,'pelvis_delta_cm':(y[:3]*100).tolist(),'change_cm':((y-second_y[0])[:3]*100).tolist()} for name,y in zip(second_variants,second_y)]
(out/'second_hitch_replay.json').write_text(json.dumps(second_result,indent=2))
print('Second hitch',json.dumps(second_result))
