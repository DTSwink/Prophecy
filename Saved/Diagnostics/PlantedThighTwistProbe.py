"""One-step sensitivity only: retain solved knee points, test NN-side thigh twist."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import pathlib,json,sys,numpy as np,torch
from scipy.spatial.transform import Rotation
torch.set_num_threads(1);torch.set_num_interop_threads(1)
root=pathlib.Path(__file__).resolve().parents[2]
rows={round(r['time']*60):r for r in map(json.loads,(root/'Saved/Diagnostics/PelvisHitch-20260920-193832/pipeline.jsonl').read_text().splitlines()) if r['actor'].endswith('_C_1')}
contract=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json').read_text())
off=np.array(json.loads((root/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())['local_offsets_m'])
sys.path.insert(0,r'C:\Users\singerie\Documents\Cursor\stepper')
from training.ik import ik_core as tl,visualize
cp=torch.load(contract['checkpoint_path'],map_location='cpu',weights_only=False);visualize.apply_simple_controller_policy(cp)
cfg=tl.TrainConfig();visualize.apply_config_dict(cfg,cp['config']);clip=tl.MotionClip(pathlib.Path(contract['seed_clip_path']),cfg,cyclic_animation=True)
model=visualize.load_model(cp,clip,cfg,torch.device('cpu')).eval()
def unit(v):return v/max(1e-12,np.linalg.norm(v))
def rot(v):
    v=np.array(v);x=unit(v[:3]);y=unit(v[3:]-x*np.dot(x,v[3:]));return np.array([x,y,np.cross(x,y)])
def swing(a,b):
    a=unit(a);b=unit(b);cross=np.cross(a,b);return Rotation.from_rotvec(unit(cross)*np.arctan2(np.linalg.norm(cross),np.dot(a,b))).as_matrix().T
def angle(a,b):return float(np.degrees(Rotation.from_matrix(a@b.T).magnitude()))
results=[]
for source in (165,169,171,173,175,177):
    nexttick=source+2;r=rows[source];base=np.array(rows[nexttick]['lower_input']);variants={'baseline':base.copy()};details={}
    raw=np.array(r['lower_input'][:41])+np.array(r['lower_delta'][:41]);pub=np.array(r['published_lower'])
    for i,side in enumerate(('left','right')):
        o=18+16*i;knee=off[18+4*i];rr=rot(raw[o:o+6]);sr=rot(pub[o:o+6]);aligned=rr@swing(knee@rr,knee@sr)
        details[side]={'raw_to_solved_deg':angle(rr,sr),'raw_swing_to_solved_deg':angle(rr,aligned),'remaining_twist_deg':angle(aligned,sr),'knee_displacement_cm':float(np.linalg.norm(knee@aligned-knee@sr)*100)}
        carry=sr.T@rot(base[o:o+6]);v=base.copy();v[o:o+6]=(aligned@carry)[:2].ravel();v[o+76:o+82]=(v[o:o+6]-v[o+41:o+47])/contract['pose_delta_scale_final']
        variants[side+'_raw_twist_solved_knee']=v
    with torch.inference_mode():ys=model(torch.tensor(np.array(list(variants.values())),dtype=torch.float32)).numpy()
    rr={'source_tick':source,'prediction_tick':nexttick,'geometry':details,'variants':[{'name':name,'pelvis_delta_cm':(y[:3]*100).tolist(),'change_cm':((y-ys[0])[:3]*100).tolist()} for name,y in zip(variants,ys)]};results.append(rr);print(json.dumps(rr))
(root/'Saved/Diagnostics/PelvisHitchInputs/planted_twist_probe.json').write_text(json.dumps(results,indent=2))
