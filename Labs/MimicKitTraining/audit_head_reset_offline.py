"""Inspect saved get-up trajectories and reconstruct critic inputs on CPU."""
import ast,io,json,zipfile,xml.etree.ElementTree as ET
from types import SimpleNamespace
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
import device_quaternion as q

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'
CP=OUT/'preserved-checkpoints/20261020_094614_uefn_getup_skew_linear_512/checkpoint_0070939.zip'
torch.set_num_threads(2)
with zipfile.ZipFile(CP) as z:
    state=torch.load(io.BytesIO(z.read('model.pt')),map_location='cpu',weights_only=False)
    replay=np.load(io.BytesIO(z.read('replay.npz')))
metadata=json.loads(str(replay['metadata']))
with zipfile.ZipFile(OUT/'getup-skew-source.zip') as z:
    xml=ET.fromstring(z.read('assets/uefn/humanoid_uefn.xml'))
    tree=ast.parse(z.read('MimicKit/mimickit/learning/rl_util.py').decode())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compute_td_lambda_return')
    scope=dict(torch=torch,base_env=SimpleNamespace(DoneFlags=SimpleNamespace(NULL=SimpleNamespace(value=0))))
    exec(compile(ast.Module(body=[function],type_ignores=[]),'deployed_rl_util','exec'),scope)
    td_return=scope['compute_td_lambda_return']
nodes=list(xml.find('worldbody').iter('body'))
parents={child:parent for parent in nodes for child in parent.findall('body')}
def inv(x):
    return x*torch.tensor([-1.,-1.,-1.,1.])
def network(obs,prefix,out):
    h=((obs-state['_obs_norm._mean'])/state['_obs_norm._std']).clamp(-10,10)
    for layer in [0,2,4]:
        h=F.relu(F.linear(h,state[f'_model.{prefix}.{layer}.weight'],state[f'_model.{prefix}.{layer}.bias']))
    return F.linear(h,state[f'_model.{out}.weight'],state[f'_model.{out}.bias'])
rows=[]
for i,m in enumerate(metadata['replay_rows']):
    if not m.get('perturbed_row') or not m.get('recovery_row'):continue
    s='' if i==0 else '_'+str(i)
    p=torch.from_numpy(replay['pose'+s]);vel=torch.from_numpy(replay['world_velocities'+s])
    data=replay['data'+s];cost=replay['loss_terms'+s][:,0]
    rotations=[];rates=[]
    for j,node in enumerate(nodes[1:],1):
        parent=nodes.index(parents[node])
        wxyz=[float(v) for v in node.get('quat','1 0 0 0').split()]
        local=torch.tensor(wxyz[1:]+wxyz[:1]).expand(len(p),4)
        rotation=q.quat_mul(inv(local),q.quat_mul(inv(p[:,parent,3:]),p[:,j,3:]))
        rotations.append(rotation)
        angular=q.quat_rotate(inv(p[:,j,3:]),vel[:,j,3:6]-vel[:,parent,3:6])
        joints=node.findall('joint')
        if len(joints)==3:rates.append(angular)
        elif len(joints)==1:
            axis=torch.tensor([float(v) for v in joints[0].get('axis','0 0 1').split()])
            rates.append((angular*axis).sum(-1,keepdim=True))
    # Recorder stores body-origin linear velocities; root observations use COM velocity.
    com=torch.tensor([float(v) for v in nodes[0].find('inertial').get('pos').split()]).expand(len(p),3)
    root_vel=vel[:,0,:3]+torch.cross(vel[:,0,3:6],q.quat_rotate(p[:,0,3:],com),dim=-1)
    physical=q.physical_observations(p[:,0,:3],p[:,0,3:],root_vel,vel[:,0,3:6],
        torch.stack(rotations,1),torch.cat(rates,-1),p[:,[2,5,8,11,14],:3],True,True)
    phase=torch.tensor(m['frame_phase'])[:,:2]
    command=torch.tensor([-1.,1.,0.,float(m['sword_drawn']),1.,1.]).expand(len(p),6)
    obs=torch.cat([physical,command,phase],-1)
    predicted=F.normalize(network(obs,'_actor_layers','_phase_out'),dim=-1)
    phase_error=float((predicted-torch.tensor(m['frame_phase'])[:,2:4]).abs().max())
    assert phase_error < .0005, 'Reconstructed inputs do not reproduce recorded phase outputs'
    values=network(obs,'_critic_layers','_critic_out').squeeze(-1).detach().numpy()
    h=p[:,2,2].numpy()/(m['head_reset_height_m']/.9)
    row=dict(row=i,world=m['world'],motion=m['recovery_motion_file'],ticks=len(data)-1,
        reset_reason=m['frame_reset_reason'][-1],head_final=float(h[-1]),head_max=float(h.max()),
        last60_head_range=[float(h[-60:].min()),float(h[-60:].max())],
        last60_reward=float(data[-60:,2].mean()),last_reward=float(data[-1,2]),
        phase_reconstruction_max_error=phase_error,
        critic_final=float(values[-1]),critic_last60_mean=float(values[-60:].mean()),
        head_ratio=h.tolist(),rewards=data[:,2].tolist(),critic_values=values.tolist(),
        last60_position_cost=float(cost[-60:].mean()))
    reward=torch.tensor([[data[-1,2]]])
    terminal_target=td_return(reward,torch.tensor([[values[-1]]]),torch.tensor([[3]]),.99,.95).item()
    known_success_target=td_return(reward,torch.tensor([[100.]]),torch.tensor([[2]]),.99,.95).item()
    row.update(current_final_critic_target=terminal_target,
        hypothetical_known_success_target=known_success_target,
        last60_reward_implied_continuing_value=float(data[-60:,2].mean()/.01))
    rows.append(row)
    print(json.dumps({k:v for k,v in row.items() if not isinstance(v,list)}))
receipt=dict(checkpoint=str(CP),iteration=metadata['iteration'],rows=rows,
    note='CPU reconstruction reproduces recorded phase outputs within 0.0005; critic values are approximate, not captured GPU outputs. Actual saved rewards/positions/outcomes are exact. Known success value is a hypothetical accounting change only; no training or reward settings changed.')
(OUT/'head-reset-offline-audit.json').write_text(json.dumps(receipt,indent=2))
