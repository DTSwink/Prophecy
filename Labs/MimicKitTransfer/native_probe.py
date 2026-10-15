"""Native closed-loop tests, with observation mapping checked against Newton."""
from probe import ROOT,OUT,SOURCE
import os,json,subprocess,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import torch,yaml
from scipy.spatial.transform import Rotation as R
import gymnasium.spaces as spaces
from omni_policy import OmniPPOModel
from envs.char_env import compute_char_obs

torch.set_num_threads(1)
runtime_path=OUT/'active_fixture.json'
runtime=json.loads(runtime_path.read_text()) if runtime_path.exists() else {}
fixture_path=Path(os.environ.get('MIMICKIT_TRANSFER_FIXTURE',str(OUT/runtime.get('executable','fixture.exe'))))
asset=SOURCE/'assets/uefn'
nodes=list(ET.parse(asset/'humanoid_uefn.xml').getroot().find('worldbody').iter('body'))
names=[n.attrib['name'] for n in nodes]
meta=json.loads((asset/'limits.json').read_text())
parents=[-1]+[names.index(next(j['parent'] for j in meta['joints'] if j['body']==name)) for name in names[1:]]
local=[R.from_quat(np.roll(np.fromstring(n.attrib.get('quat','1 0 0 0'),sep=' '),-1)) for n in nodes]
keys=[names.index(n) for n in ['head','right_hand','left_hand','right_foot','left_foot']]
offsets=np.array([np.fromstring(nodes[i].find('geom').attrib['pos'],sep=' ') for i in keys])
# Head termination uses the head collider, not the first neck collider.
offsets[0]=np.fromstring(nodes[keys[0]].find("geom[@name='head_shape0']").attrib['pos'],sep=' ')

class SpaceOnly:
    def get_obs_space(self):return spaces.Box(-np.inf,np.inf,(151,),dtype=np.float32)
    def get_action_space(self):return spaces.Box(-2*np.pi,2*np.pi,(34,),dtype=np.float32)
model=OmniPPOModel(yaml.safe_load((OUT/'checkpoint/agent_config.yaml').read_text())['model'],SpaceOnly())
checkpoint=torch.load(OUT/'checkpoint/model.pt',map_location='cpu',weights_only=False)
model.load_state_dict({k[len('_model.'):]:v for k,v in checkpoint.items() if k.startswith('_model.')});model.eval()

def load_actor(path):
    global checkpoint
    checkpoint=torch.load(path,map_location='cpu',weights_only=True)
    model.load_state_dict({k[len('_model.'):]:v for k,v in checkpoint.items() if k.startswith('_model.')})
    model.eval()
def actor(obs):
    obs=torch.as_tensor(obs,dtype=torch.float32).reshape(1,151)
    with torch.no_grad():
        norm=((obs-checkpoint['_obs_norm._mean'])/checkpoint['_obs_norm._std']).clamp(-10,10)
        return (model.eval_actor(norm).mode*checkpoint['_a_norm._std']+checkpoint['_a_norm._mean']).numpy()[0]

def observation(state,commands):
    rot=R.from_quat(state[:,3:7]);joint=[];vel=[]
    for i in range(1,15):
        joint.append((local[i].inv()*rot[parents[i]].inv()*rot[i]).as_quat())
        angular=rot[i].inv().apply(state[i,10:13]-state[parents[i],10:13])
        vel.extend(angular if len(nodes[i].findall('joint'))==3 else [angular[2]])
    def t(a):return torch.as_tensor(np.asarray(a)[None],dtype=torch.float32)
    physical=compute_char_obs(t(state[0,:3]),t(state[0,3:7]),t(state[0,7:10]),t(state[0,10:13]),t(joint),t(vel),t(state[keys,:3]),True,True).numpy()[0]
    return np.r_[physical,commands]

class Native:
    def __init__(self,initial):
        descriptor,initial_name=tempfile.mkstemp(prefix='native-initial-',suffix='.txt',dir=OUT)
        os.close(descriptor);initial_path=Path(initial_name)
        np.savetxt(initial_path,initial,fmt='%.12g')
        env=dict(os.environ);env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env.get('PATH','')
        self.log=open(OUT/'native-stderr.log','a')
        self.p=subprocess.Popen([str(fixture_path),str(initial_path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,env=env)
        try:self.initial=self.read()
        finally:initial_path.unlink(missing_ok=True)
    def read(self):
        line=self.p.stdout.readline()
        if not line:raise RuntimeError('Native fixture exited; see native-stderr.log')
        return json.loads(line)
    def request(self,line):self.p.stdin.write(line+'\n');self.p.stdin.flush();return self.read()
    def close(self):
        if self.p.poll() is None:self.p.stdin.write('quit\n');self.p.stdin.flush();self.p.wait(timeout=5)
        self.log.close()

def main():
    reports=[];mapping=[]
    tag='jolt_training_contact' if os.getenv('TRANSFER_TRAINING_CONTACT') else 'jolt'
    tag=os.environ.get('MIMICKIT_TRANSFER_TAG',runtime.get('tag',tag))
    for path in sorted(OUT.glob('newton_phase_*.npz')):
        if len(path.stem.split('_'))!=3:continue
        data=np.load(path)
        if 'physical' not in data:continue
        states=data['physical'];obs=data['obs'][:,0]
        # Reset cache body velocities are zero before the first Newton step.
        # Start at tick1, where generalized and body states are synchronized.
        for tick in range(1,len(states)):
            reconstructed=observation(states[tick],obs[tick,-5:]);error=np.max(np.abs(reconstructed-obs[tick]))
            mapping.append(float(error))
            if tick<len(data['actions']):np.testing.assert_allclose(actor(obs[tick]),data['actions'][tick,0],rtol=2e-5,atol=3e-6)
        assert max(mapping)<5e-4,('Observation mapping mismatch',max(mapping))
        initial=states[1];native=Native(initial);current=np.array(native.initial['bodies']);history=[current];distances=[];impulses=[]
        native_actions=[];motor_fractions=[];max_init=float(np.max(np.abs(current-initial)))
        try:
            properties=native.request('inspect')['body_properties']
            for i,name in enumerate(names):
                expected=json.loads((asset/'physics.json').read_text())['bodies'][name]
                np.testing.assert_allclose(properties[i][0],expected['mass'],rtol=2e-5)
                np.testing.assert_allclose(properties[i][1:4],expected['com'],atol=2e-6)
                np.testing.assert_allclose(np.array(properties[i][4:13]).reshape(3,3),np.linalg.inv(expected['inertia']),atol=2e-3,rtol=2e-5)
            for tick in range(1,len(data['actions'])):
                action=actor(observation(current,obs[tick,-5:]));native_actions.append(action)
                output=native.request('step '+' '.join(map(str,action)));current=np.array(output['bodies']);history.append(current);impulses.append(output['ground_vertical_impulse_ns'])
                motor_fractions.append(output['max_motor_fraction'])
                assert np.isfinite(current).all()
                target=data['targets'][tick].copy();target[:,:2]+=current[0,:2]-target[0,:2]
                actual_c=current[keys,:3]+R.from_quat(current[keys,3:7]).apply(offsets)
                target_c=target[keys,:3]+R.from_quat(target[keys,3:7]).apply(offsets)
                distance=np.linalg.norm(actual_c-target_c,axis=-1);distances.append(distance)
                if distance.max()>.27:break
        finally:native.close()
        np.savez_compressed(OUT/path.name.replace('newton',tag),states=history,dist=distances,actions=native_actions,ground_impulses=impulses,motor_fraction=motor_fractions)
        report=dict(phase=path.stem.split('_')[-1],jolt_ticks=len(distances),newton_ticks=len(data['actions'])-1,
                    max_target_distance_m=float(np.max(distances)),worst_body=names[keys[int(np.argmax(distances[-1]))]],
                    initial_state_max_error=max_init,observations_max_error=max(mapping),ground_impulse_ns=float(np.sum(impulses)),
                    jolt_root_height_m=float(current[0,2]),termination_check='27cm only; stock contact/pose failure not yet ported')
        report['ticks_with_motor_saturation']=int(np.sum(np.array(motor_fractions)>.999))
        reports.append(report);print(json.dumps(report),flush=True)
    (OUT/f'{tag}_report.json').write_text(json.dumps(reports,indent=2))
if __name__=='__main__':main()
