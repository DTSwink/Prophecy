"""Isolated viewer experiment; does not modify the running viewer or its files."""
import sys,inspect,textwrap,json,dataclasses
from pathlib import Path
sys.path.insert(0,r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/ParryAndDodge/temp_dodge_reference_viz')
import inference as m
import numpy as np
import torch
out=Path(__file__).parent
distance=float(sys.argv[1]) if len(sys.argv)>1 else .823797974
suffix='_60cm' if abs(distance-.6)<1e-5 else ''
src=textwrap.dedent(inspect.getsource(m.Engine.generate))
src=src.replace("        limb = ATTACK_LIMBS[family]", "        limb = ATTACK_LIMBS[family]")
src=src.replace("    limb = ATTACK_LIMBS[family]", "    self.debug_result = result\n    self.debug_attack = (p,r,names)\n    limb = ATTACK_LIMBS[family]")
ns={};exec(src,m.__dict__,ns);m.Engine.generate=ns['generate']
engine=m.Engine();original=m.rollout;reports=[]
def measure(a,e,start,label):
    c,axes=m.defense_obbs(a.positions,a.rotations,engine.geometry)
    masks=m.label_masks([0],engine.geometry.names,'cpu')
    harm=torch.zeros_like(masks[2]);harm[...,engine.geometry.names.index('head')]=True
    _,contact=m.harmful_contact_loss(c,axes,e.collider[...,:3],e.collider_axes,e.attack_half,engine.geometry,
        torch.zeros_like(masks[1]),harm,torch.ones((1,e.valid.shape[1]-1),dtype=torch.bool),all_contacts=True)
    entry=dict(label=label,start=start,head_hit=bool(contact.harmful_hit[0]),
        head_contact_frame=float(contact.first_harm_time[0])+start,
        head=a.positions[0,:,engine.skeleton.body_names.index('head')].tolist())
    reports.append(entry)
    return a
def wrap(agent,e):
    print('ATTACK RESULT KEYS',list(engine.debug_result),flush=True)
    armed=np.asarray(engine.debug_result['armed'][0]).reshape(-1)
    gate=int(np.flatnonzero(armed>.5)[0]);print('ARMED',gate,armed.tolist(),flush=True)
    base=measure(original(agent,e),e,0,'viewer_original')
    start=max(0,gate-1)
    seq={'pelvis','collider','collider_axes','event','times','valid'}
    cropped=dataclasses.replace(e,**{k:getattr(e,k)[:,start:].clone() for k in seq})
    measure(original(agent,cropped),cropped,start,'armed_gate_correct_collider')
    immediate_start=max(0,gate-2)
    immediate=dataclasses.replace(e,**{k:getattr(e,k)[:,immediate_start:].clone() for k in seq})
    measure(original(agent,immediate),immediate,immediate_start,'first_output_on_armed_frame')
    p,r,names=engine.debug_attack;j=names.index('hand_l')
    f=r[:,j,0];f=f/np.linalg.norm(f,axis=-1,keepdims=True)
    u=r[:,j,1]-f*np.sum(r[:,j,1]*f,axis=-1,keepdims=True);u/=np.linalg.norm(u,axis=-1,keepdims=True)
    side=np.cross(u,f);side/=np.linalg.norm(side,axis=-1,keepdims=True)
    axes=np.stack([f,side,np.cross(f,side)],axis=1)
    center=p[:,j]+f*.0725-u*.0025
    wrong=torch.tensor(np.concatenate([center,axes[:,:2].reshape(len(p),6)],-1))[None]
    doc=json.loads((out.parents[2]/'Content/locomotion/NN/defense/parry_colliders.json').read_text())
    half=next(x['half'] for x in doc['colliders'] if x['name']=='hand_l')
    old=dataclasses.replace(cropped,collider=wrong[:,start:],collider_axes=torch.tensor(axes)[None,start:],attack_half=torch.tensor(half)[None])
    measure(original(agent,old),cropped,start,'armed_gate_old_hand_input_actual_forearm_contact')
    (out/f'gate_results{suffix}.json').write_text(json.dumps(dict(armed=gate,reports=reports)))
    return base
m.rollout=wrap
with torch.inference_mode():
    data=engine.generate(dict(attack='hookL',distance=distance,orbit=0,facing=0))
(out/('viewer_hookL_60cm.json' if suffix else 'viewer_hookL_82cm.json')).write_text(json.dumps(data))
print(json.dumps([{k:v for k,v in r.items() if k!='head'} for r in reports]),flush=True)
