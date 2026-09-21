"""Offline only: ideal followers, no UE process/asset modifications.

The displayed-pose surrogate interpolates unrebased published lower states.
This isolates publication delay/root-frame differences; it is NOT a Jolt replay.
Clamps, contacts, rigid-calf postprocessing and physics lag are not simulated.
"""
import os
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
import sys, json, ctypes, hashlib, time
from pathlib import Path
import numpy as np
import torch
from scipy.spatial.transform import Rotation
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.path.insert(0, r'C:\Users\singerie\Documents\Cursor\stepper')
from training.ik import ik_core as tl, train_simple_ae_controller as ctl, visualize

def rotations(v, offset):
    return Rotation.from_matrix(tl.rotation_6d_to_matrix(v[:,offset:offset+6]).numpy())

def mixrot(a,b,t):
    return a * Rotation.from_rotvec((a.inv()*b).as_rotvec()*np.asarray(t).reshape(-1,1))

def putrot(v, offset, r):
    v[:,offset:offset+6]=tl.rotmat_to_6d(torch.tensor(r.as_matrix(),dtype=torch.float32))

def interpolate(a,b,alpha):
    out=a*(1-alpha)+b*alpha
    for o in (3,12,18,28,34): putrot(out,o,mixrot(rotations(a,o),rotations(b,o),alpha))
    return out

def main():
    is_run='--run' in sys.argv
    output=OUT/('run' if is_run else 'walk'); output.mkdir(exist_ok=True)
    contract=json.loads((ROOT/'Content/locomotion/NN'/('prophecy_lower_body_runtime.json' if is_run else 'prophecy_lower_body_walk_july5_runtime.json')).read_text())
    cp=torch.load(contract['checkpoint_path'],map_location='cpu',weights_only=False)
    visualize.apply_simple_controller_policy(cp)
    cfg=tl.TrainConfig(); visualize.apply_config_dict(cfg,cp['config'])
    cfg.device='cpu'; cfg.cyclic_animation=True
    clip=tl.MotionClip(Path(contract['seed_clip_path']),cfg,cyclic_animation=True)
    store=ctl.SimpleClipStore([clip],cfg,torch.device('cpu'))
    model=visualize.load_model(cp,clip,cfg,torch.device('cpu')).eval()
    ctl.FOOT_ROLL_INTEGRATION_STEPS=contract['foot_roll']['integration_steps']
    cases=[('no_feedback',1000,1000,'display'),('aligned_perfect_0',0,0,'aligned'),
           ('display_0cm_0deg',0,0,'display'),('display_1cm_5deg',1,5,'display'),
           ('display_5cm_15deg',5,15,'display'),('display_10cm_30deg',10,30,'display'),
           ('display_linear_only',0,1000,'display'),('display_angular_only',1000,0,'display'),
           ('latest_unrebased_0',0,0,'latest'),('display_rebased_0',0,0,'rebased'),
           ('latest_rebased_0',0,0,'latest_rebased')]
    n=len(cases); ids=torch.zeros(n,dtype=torch.long)
    previous,_,_=ctl.target_state(store,ids,torch.zeros(n,dtype=torch.long))
    current,_,_=ctl.target_state(store,ids,torch.ones(n,dtype=torch.long))
    # Initialization only; ignored by metrics after 60 frames.
    older=previous.clone(); newest=current.clone(); hist=current.clone()
    pub_root_old=store.root_state(ids,torch.zeros(n,dtype=torch.long))[:2]
    pub_root_new=store.root_state(ids,torch.ones(n,dtype=torch.long))[:2]
    payload=ctl.payload_slice(store)
    samples=[]; states=[]; errors=[]; pins=[]; angles=[]; affected=[]; root_steps=[]; root_turns=[]
    started=time.time()
    with torch.inference_mode():
      for frame in range(1,241):
        idx=torch.full((n,),frame,dtype=torch.long)
        sampled=interpolate(older,newest,.5)
        # Ideal completed physical pose expressed relative to its displayed root.
        display_root_pos=(pub_root_old[0]+pub_root_new[0])*.5
        # Forward loop has constant root rotation; use current published rotation.
        cur_root_pos,cur_root_rot,*_=store.root_state(ids,idx)
        root_steps.append(float(torch.linalg.vector_norm(cur_root_pos[0]-pub_root_new[0][0])*100))
        root_turns.append(float(np.linalg.norm((Rotation.from_matrix(pub_root_new[1][0].numpy()).inv()*Rotation.from_matrix(cur_root_rot[0].numpy())).as_rotvec())*180/np.pi))
        rebased=ctl.rebase_output_vector_root(store,sampled,display_root_pos,pub_root_new[1],cur_root_pos,cur_root_rot)
        latest_rebased=ctl.rebase_output_vector_root(store,newest,pub_root_new[0],pub_root_new[1],cur_root_pos,cur_root_rot)
        for i,(_,_,_,source) in enumerate(cases):
          if source=='aligned': sampled[i]=current[i]
          if source=='latest': sampled[i]=newest[i]
          if source=='rebased': sampled[i]=rebased[i]
          if source=='latest_rebased': sampled[i]=latest_rebased[i]
        error=torch.stack([torch.linalg.vector_norm(sampled[:,o:o+3]-current[:,o:o+3],dim=1)*100 for o in (9,25)],1)
        ang=np.stack([np.linalg.norm((rotations(current,o).inv()*rotations(sampled,o)).as_rotvec(),axis=1)*180/np.pi for o in (12,18,28,34)],1)
        errors.append(error.numpy()); angles.append(ang)
        feedback=current.clone() # pelvis explicitly excludes feedback
        linear=torch.tensor([c[1]/100 for c in cases]); angular=np.array([c[2] for c in cases])
        for o in (9,25):
          delta=sampled[:,o:o+3]-current[:,o:o+3]; size=torch.linalg.vector_norm(delta,dim=1)
          feedback[:,o:o+3]+=delta*(torch.clamp(size-linear,min=0)/size.clamp_min(1e-10))[:,None]
        for o in (12,18,28,34):
          a=rotations(current,o); b=rotations(sampled,o)
          degree=np.linalg.norm((a.inv()*b).as_rotvec(),axis=1)*180/np.pi
          weight=np.maximum(degree-angular,0)/np.maximum(degree,1e-10)
          putrot(feedback,o,mixrot(a,b,weight))
          # Preserve exact copy inside tolerance, as in native code.
          mask=torch.tensor(degree<=angular+1e-7); feedback[mask,o:o+6]=current[mask,o:o+6]
        for o in (24,40):
          delta=sampled[:,o]-current[:,o]; size=delta.abs()*90
          feedback[:,o]+=delta*((size-torch.tensor(angular,dtype=torch.float32)).clamp_min(0)/size.clamp_min(1e-10))
        changed=torch.any(feedback!=current,dim=1)
        previous[changed]=hist[changed] if frame>1 else feedback[changed]
        current[changed]=feedback[changed]
        hist=current.clone()
        affected.append(changed.numpy()); samples.append(current.numpy().copy())
        inputs=ctl.build_controller_input(store,ids,idx,previous,current,previous[:,:3],current[:,:3],previous[:,payload],current[:,payload])
        raw=ctl.model_raw_output(model,inputs,current,store)
        transition,_,pin=ctl.clean_output_vector_pair_with_pin_prob(raw,store,current,previous)
        following,_,_=ctl.advance_transition_state(store,ids,idx,transition)
        states.append(following.numpy()); pins.append(pin.numpy())
        previous=current; current=following
        older=newest; newest=transition
        pub_root_old=pub_root_new; pub_root_new=(cur_root_pos,cur_root_rot)
        if frame%60==0: print('frame',frame,'seconds',round(time.time()-started,1),flush=True)
    states=np.array(states); errors=np.array(errors); angles=np.array(angles); pins=np.array(pins); affected=np.array(affected)
    metrics={}
    for i,(name,_,_,_) in enumerate(cases):
      s=states[60:,i]; ref=states[60:,0]
      foot=s[:,[9,10,11,25,26,27]].reshape(-1,2,3)
      ref_foot=ref[:,[9,10,11,25,26,27]].reshape(-1,2,3)
      metrics[name]={'foot_target_difference_mean_cm':float(np.linalg.norm(foot-ref_foot,axis=-1).mean()*100),
        'foot_relative_range_cm':(np.ptp(foot,axis=0)*100).tolist(),
        'perfect_follower_apparent_error_mean_cm':float(errors[60:,i].mean()),
        'perfect_follower_apparent_error_p95_cm':float(np.percentile(errors[60:,i],95)),
        'apparent_rotation_error_mean_deg':float(angles[60:,i].mean()),
        'apparent_rotation_error_p95_deg':float(np.percentile(angles[60:,i],95)),
        'feedback_active_fraction':float(affected[60:,i].mean()),
        'both_pinned_fraction':float(np.all(pins[60:,i]>.99,axis=-1).mean())}
    report={'method':__doc__,'checkpoint':contract['checkpoint_path'],'checkpoint_sha256':hashlib.sha256(Path(contract['checkpoint_path']).read_bytes()).hexdigest(),'cases':cases,'metrics':metrics,'seconds':time.time()-started,
      'root_step_median_cm':float(np.median(root_steps[2:])), 'root_turn_max_deg':max(root_turns[2:]), 'foot_roll_integration_steps':ctl.FOOT_ROLL_INTEGRATION_STEPS}
    (output/'results.json').write_text(json.dumps(report,indent=2))
    np.savez_compressed(output/'rollouts.npz',states=states,errors=errors,angles=angles,pins=pins,feedback_active=affected)
    print(json.dumps(metrics,indent=2),flush=True)

if __name__=='__main__': main()
