"""Frozen-checkpoint, identical-state recovery transfer audit. Never trains."""
import os, sys, json, argparse, time, subprocess, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023'
SOURCE = Path(os.environ.get('GETUP_AUDIT_SOURCE',OUT/'source'))
os.environ['PYGLET_HEADLESS'] = 'true'
os.environ['OMP_NUM_THREADS'] = '1'
sys.path[:0] = [str(SOURCE/'pipeline'), str(SOURCE/'MimicKit/mimickit'),
               str(ROOT/'Saved/MimicKitUEFN/dependencies')]
import numpy as np
import torch, yaml
from scipy.spatial.transform import Rotation as R
import xml.etree.ElementTree as ET
from omni_policy import OmniPPOModel
from envs.char_env import compute_char_obs
import gymnasium.spaces as spaces
torch.set_num_threads(1)

ASSET = SOURCE/'assets/uefn'
nodes = list(ET.parse(ASSET/'humanoid_uefn.xml').getroot().find('worldbody').iter('body'))
names = [b.get('name') for b in nodes]
limits = json.loads((ASSET/'limits.json').read_text())
physics = json.loads((ASSET/'physics.json').read_text())
parents = [-1]+[names.index(next(j['parent'] for j in limits['joints'] if j['body']==n)) for n in names[1:]]
local = [R.from_quat(np.roll(np.fromstring(n.get('quat','1 0 0 0'),sep=' '),-1)) for n in nodes]
com = np.array([physics['bodies'][n]['com'] for n in names])
keys = [names.index(n) for n in ['head','right_hand','left_hand','right_foot','left_foot']]

def tensor(a): return torch.as_tensor(np.asarray(a),dtype=torch.float32)

def joint_state(state):
    rot = R.from_quat(state[:,3:7]); joints=[]; vel=[]
    for i in range(1,15):
        joints.append((local[i].inv()*rot[parents[i]].inv()*rot[i]).as_quat())
        angular=rot[i].inv().apply(state[i,10:13]-state[parents[i],10:13])
        vel.extend(angular if len(nodes[i].findall('joint'))==3 else [angular[2]])
    return np.asarray(joints),np.asarray(vel)

def observation(state, row, phase):
    # state velocities are world COM velocities, matching Newton's floating root.
    joints,vel=joint_state(state)
    physical=compute_char_obs(tensor(state[None,0,:3]),tensor(state[None,0,3:7]),
        tensor(state[None,0,7:10]),tensor(state[None,0,10:13]),tensor(joints[None]),
        tensor(vel[None]),tensor(state[None,keys,:3]),True,True)
    command=tensor([[-1.,1.,0.,float(row['sword_drawn']),*row['arm_enabled'],*phase]])
    return torch.cat((physical,command),-1)

def observation_batch(states, rows, phase):
    # The audit's original per-world SciPy loop idled the GPU between ticks.
    # Batch exactly the same coordinate conversion and frozen policy inputs.
    rotations=[R.from_quat(states[:,i,3:7]) for i in range(15)]
    joints=[];vel=[]
    for i in range(1,15):
        joints.append((local[i].inv()*rotations[parents[i]].inv()*rotations[i]).as_quat())
        angular=rotations[i].inv().apply(states[:,i,10:13]-states[:,parents[i],10:13])
        vel.append(angular if len(nodes[i].findall('joint'))==3 else angular[:,2:3])
    physical=compute_char_obs(tensor(states[:,0,:3]),tensor(states[:,0,3:7]),
        tensor(states[:,0,7:10]),tensor(states[:,0,10:13]),tensor(np.stack(joints,axis=1)),
        tensor(np.concatenate(vel,axis=1)),tensor(states[:,keys,:3]),True,True)
    command=tensor([[-1.,1.,0.,float(row['sword_drawn']),*row['arm_enabled'],*ph] for row,ph in zip(rows,phase)])
    return torch.cat((physical,command),-1)

class Policy:
    def __init__(self,tag):
        class SpaceOnly:
            def get_obs_space(self):return spaces.Box(-np.inf,np.inf,(154,),dtype=np.float32)
            def get_action_space(self):return spaces.Box(-np.inf,np.inf,(34,),dtype=np.float32)
        self.saved=torch.load(OUT/tag/'model.pt',map_location='cpu',weights_only=True)
        self.model=OmniPPOModel(yaml.safe_load((OUT/tag/'agent_config.yaml').read_text())['model'],SpaceOnly())
        self.model.load_state_dict({k[7:]:v for k,v in self.saved.items() if k.startswith('_model.')})
        self.model.eval()
        self.bound=tensor(json.loads((OUT/tag/'velocity_command_bounds.json').read_text())['command_bound_rad_s'])
    @torch.no_grad()
    def __call__(self,obs):
        s=self.saved
        norm=((obs-s['_obs_norm._mean'])/s['_obs_norm._std']).clamp(-10,10)
        h=self.model._actor_layers(norm)
        action=self.model._action_dist(h).mode*s['_a_norm._std']+s['_a_norm._mean']
        phase=torch.nn.functional.normalize(self.model._phase_out(h),dim=-1,eps=1e-6)
        return action.clamp(-self.bound,self.bound).numpy(),phase.numpy()

def replay(tag,index):
    a=np.load(OUT/tag/'replay.npz'); m=json.loads(str(a['metadata']))['replay_rows'][index]
    suffix='' if index==0 else '_'+str(index)
    pose=a['pose'+suffix].copy(); vel=a['world_velocities'+suffix][:,:,:6].copy()
    # Recorder stores body-origin linear velocity. Jolt/Newton state is COM.
    offset=R.from_quat(pose[:,:,3:].reshape(-1,4)).apply(np.tile(com,(len(pose),1))).reshape(-1,15,3)
    vel[:,:,:3]+=np.cross(vel[:,:,3:],offset)
    states=np.concatenate((pose,vel),-1)
    if tag=='custom' and not np.any(vel[0]):
        # Old custom backend lacked refresh_body_velocities at reset. Recover the
        # actual generalized initial velocity, not the zero-valued replay cache.
        if m['perturbed_plus_row']:
            spin=np.array(m['initial_root_angular_velocity_rad_s'])
            linear=np.array(m['initial_pelvis_origin_velocity_m_s'])+np.cross(spin,offset[0,0])
            dof=np.array(m['initial_joint_velocity'])
        else:
            from anim.motion_lib import MotionLib
            from anim.mjcf_char_model import MJCFCharModel
            kin=MJCFCharModel('cpu');kin.load(str(ASSET/'humanoid_uefn.xml'))
            lib=MotionLib(str(SOURCE/'motions/recovery'/Path(m['recovery_motion_file']).name),kin,'cpu')
            _,_,v,w,_,dv=lib.calc_motion_frame(torch.tensor([0]),torch.tensor([m['recovery_start_seconds']]))
            yaw=R.from_euler('z',m['getup_world_yaw_degrees'],degrees=True)
            linear=yaw.apply(v[0].numpy());spin=yaw.apply(w[0].numpy());dof=dv[0].numpy()
        states[0,0,7:10]=linear;states[0,0,10:13]=spin
        rotations=R.from_quat(pose[0,:,3:]);at=0
        for b in range(1,15):
            ball=len(nodes[b].findall('joint'))==3
            joint_velocity=dof[at:at+3] if ball else np.array([0.,0.,dof[at]])
            at+=3 if ball else 1
            parent=parents[b];omega=states[0,parent,10:13]+rotations[b].apply(joint_velocity)
            anchor=pose[0,b,:3]
            parent_center=pose[0,parent,:3]+offset[0,parent]
            linear=states[0,parent,7:10]+np.cross(states[0,parent,10:13],anchor-parent_center)+np.cross(omega,offset[0,b])
            states[0,b,7:10]=linear;states[0,b,10:13]=omega
    return m,states

def outcome(state,tick,row):
    head=state[2,2]
    origin_vel=state[2,7:10]-np.cross(state[2,10:13],R.from_quat(state[2,3:7]).apply(com[2]))
    success=(head>row['head_reset_height_m'] and np.all(state[[11,14],2]<row['success_max_feet_height_m'])
             and abs(origin_vel[2])<row['success_max_head_vertical_speed_m_s'])
    fail=(tick>row['getup_failure_pelvis_after_tick'] and state[0,2]>=row['getup_failure_pelvis_height_m'])
    low=(tick>=row['getup_low_head_failure_tick'] and head<=row['head_height_loss_target_m']*.5)
    # Failure takes precedence in the production environment.
    return (1 if fail or low else 2 if success else 3 if tick>=row['getup_max_ticks'] else 0)

class Jolt:
    def __init__(self,state):
        f=tempfile.NamedTemporaryFile(mode='w',suffix='.txt',dir=OUT,delete=False)
        np.savetxt(f,state,fmt='%.12g');f.close()
        env=dict(os.environ);env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env.get('PATH','')
        self.err=open(OUT/'jolt-stderr.log','a')
        self.p=subprocess.Popen([os.environ.get('GETUP_JOLT_FIXTURE',str(OUT/'fixture.exe')),f.name],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,env=env)
        try:self.initial=self.read()
        finally:Path(f.name).unlink()
    def read(self):
        line=self.p.stdout.readline()
        if not line:raise RuntimeError('Jolt fixture exited; see jolt-stderr.log')
        return json.loads(line)
    def request(self,line):self.p.stdin.write(line+'\n');self.p.stdin.flush();return self.read()
    def close(self):
        if self.p.poll() is None:self.p.stdin.write('quit\n');self.p.stdin.flush();self.p.wait(5)
        self.err.close()

def check_mapping(tag):
    policy=Policy(tag);errors=[]
    for i in range(2,20):
        row,states=replay(tag,i)
        for tick,state in enumerate(states):
            phase=row['frame_phase'][tick]
            _,pred=policy(observation(state,row,phase[:2]))
            errors.append(float(np.max(abs(pred[0]-phase[2:4]))))
    report=dict(checkpoint=tag,frames=len(errors),max_phase_reconstruction_error=max(errors),median=float(np.median(errors)))
    print(json.dumps(report),flush=True)
    (OUT/(tag+'-mapping.json')).write_text(json.dumps(report,indent=2))
    assert max(errors)<.001,report

def jolt_test(tag,indices,label):
    policy=Policy(tag);reports=[]
    for index in indices:
        row,states=replay(tag,index);state=states[0];phase=np.array(row['frame_phase'][0][:2])
        simulation=Jolt(state);current=np.array(simulation.initial['bodies']);init_error=float(np.max(abs(current-state)))
        np.testing.assert_allclose(current,state,atol=1e-5,rtol=1e-5)
        history=[current];actions=[];phases=[phase];contacts=[];result=0
        try:
            props=simulation.request('inspect')['body_properties']
            for i,n in enumerate(names):
                expected=physics['bodies'][n]
                np.testing.assert_allclose(props[i][0],expected['mass'],rtol=2e-5)
                np.testing.assert_allclose(props[i][1:4],com[i],atol=2e-6)
                np.testing.assert_allclose(np.array(props[i][4:13]).reshape(3,3),np.linalg.inv(expected['inertia']),atol=2e-3,rtol=2e-5)
            for tick in range(1,181):
                action,pred=policy(observation(current,row,phase));phase=pred[0]
                output=simulation.request('step '+' '.join(map(str,action[0])))
                current=np.array(output['bodies']);history.append(current);actions.append(action[0]);phases.append(phase)
                contacts.append(output['ground_vertical_impulse_ns'])
                assert np.isfinite(current).all()
                result=outcome(current,tick,row)
                if result:break
        finally:simulation.close()
        p=OUT/f'{tag}-row{index}-jolt-{label}'
        np.savez_compressed(p.with_suffix('.npz'),states=history,actions=actions,phase=phases,ground_impulses=contacts)
        result=dict(checkpoint=tag,row=index,backend=getattr(simulation,'backend_label','project Jolt DLL standalone fixture'),label=label,
                    terminal=result,ticks=tick,recorded_terminal=row['terminal_flag'],recorded_ticks=len(states)-1,
                    blend=row['whole_pose_blend'],plus=row['perturbed_plus_row'],initial_error=init_error,
                    head_final_m=float(current[2,2]),pelvis_final_m=float(current[0,2]),
                    original_head_m=float(state[2,2]))
        reports.append(result);print(json.dumps(result),flush=True)
    (OUT/f'jolt-{tag}-{label}.json').write_text(json.dumps(reports,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['mapping','jolt']);p.add_argument('--checkpoint',default='native');p.add_argument('--rows',default='3,8,9,16');p.add_argument('--label',default='baseline');a=p.parse_args()
    if a.mode=='mapping':check_mapping(a.checkpoint)
    else:jolt_test(a.checkpoint,list(map(int,a.rows.split(','))),a.label)
