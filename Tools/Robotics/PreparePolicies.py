"""Export the requested frozen robot actors; no training, editor or cloud access."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
LOCO = ROOT/'Saved/MimicKitLocomotion/unreal-handoff-20261026'
RECOVERY = ROOT/'Exports/MimicKitEquipment/Recovery_Pelvismax161960_Unreal_20261026'
OUT = ROOT/'Content/locomotion/NN/robots'
REPORT = ROOT/'Saved/Diagnostics/RobotLocomotion20261026'
os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.path[:0] = [str(ROOT/'Saved/MimicKitUEFN/dependencies'),
               str(ROOT/'Saved/SlashPythonDependencies'),
               str(LOCO/'reference/pipeline'),
               str(ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023/source/MimicKit/mimickit')]
import numpy as np
import torch
import yaml
import gymnasium.spaces as spaces
import onnxruntime as ort
# Load the exact frozen model definition without importing training/video agents.
model_source = (LOCO/'reference/pipeline/omni_policy.py').read_text(encoding='utf-8')
model_source = model_source.split('\nclass OmniPPOAgent(')[0].replace('from learning.ppo_agent import PPOAgent', '')
model_namespace = {}
exec(compile(model_source, str(LOCO/'reference/pipeline/omni_policy.py'), 'exec'), model_namespace)
OmniPPOModel = model_namespace['OmniPPOModel']


class SpaceOnly:
    def get_obs_space(self):
        return spaces.Box(-np.inf, np.inf, (154,), dtype=np.float32)

    def get_action_space(self):
        return spaces.Box(-np.inf, np.inf, (34,), dtype=np.float32)


class Actor(torch.nn.Module):
    def __init__(self, model, saved):
        super().__init__()
        self.layers = model._actor_layers
        self.motor = model._action_dist._mean_net
        self.phase = model._phase_out
        for name, key in [('obs_mean', '_obs_norm._mean'), ('obs_std', '_obs_norm._std'),
                          ('action_mean', '_a_norm._mean'), ('action_std', '_a_norm._std')]:
            self.register_buffer(name, saved[key])

    def forward(self, observations):
        hidden = self.layers(((observations-self.obs_mean)/self.obs_std).clamp(-10, 10))
        actions = (self.motor(hidden)*self.action_std+self.action_mean).clamp(-2*np.pi, 2*np.pi)
        return actions, torch.nn.functional.normalize(self.phase(hidden), dim=-1, eps=1e-6)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    torch.set_num_threads(1)
    saved = torch.load(LOCO/'model.pt', map_location='cpu', weights_only=True)
    config = yaml.safe_load((LOCO/'agent_config.yaml').read_text())
    model = OmniPPOModel(config['model'], SpaceOnly()).eval()
    model.load_state_dict({k[7:]:v for k,v in saved.items() if k.startswith('_model.')})
    wrapper = Actor(model, saved).eval()
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    path = OUT/'clanker_214358.onnx'
    torch.onnx.export(wrapper, torch.zeros(1,154), str(path), dynamo=False, opset_version=17,
        input_names=['observations'], output_names=['joint_velocity_rad_s', 'next_phase'],
        dynamic_axes={n:{0:'batch'} for n in ('observations','joint_velocity_rad_s','next_phase')})
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = opts.inter_op_num_threads = 1
    runtime = ort.InferenceSession(str(path), sess_options=opts, providers=['CPUExecutionProvider'])
    # Recorded recovery states exercise the shared physical observation contract;
    # locomotion commands are replaced with every supported gait/direction.
    recorded = np.load(RECOVERY/'validation/inference_vectors.npz')['observations']
    samples = []
    for gait in (-1,0,1):
        for angle in np.linspace(0,2*np.pi,8,endpoint=False):
            obs=recorded.copy();obs[:,146]=gait;obs[:,147]=np.cos(angle);obs[:,148]=np.sin(angle)
            samples.append(obs)
    obs=np.concatenate(samples).astype(np.float32)
    with torch.inference_mode():
        tensor=torch.from_numpy(obs)
        normalized=((tensor-saved['_obs_norm._mean'])/saved['_obs_norm._std']).clamp(-10,10)
        expected=[(model.eval_actor(normalized).mode*saved['_a_norm._std']+saved['_a_norm._mean']).clamp(-2*np.pi,2*np.pi).numpy(),
                  torch.nn.functional.normalize(model.eval_phase(normalized),dim=-1,eps=1e-6).numpy()]
    actual=runtime.run(None,{'observations':obs})
    errors=[]
    for a,b in zip(actual,expected):
        np.testing.assert_allclose(a,b,atol=5e-5,rtol=5e-5)
        errors.append(float(np.max(np.abs(a-b))))
    recovery_path=OUT/'getup_161960.onnx'
    shutil.copyfile(RECOVERY/'policy/recovery_actor.onnx', recovery_path)
    # Plain JSON vectors are directly consumable by the Unreal parity probe.
    vectors={'observations':obs[:32].tolist(),'joint_velocity_rad_s':expected[0][:32].tolist(),'next_phase':expected[1][:32].tolist()}
    (REPORT/'clanker-vectors.json').write_text(json.dumps(vectors),encoding='utf-8')
    rec=np.load(RECOVERY/'validation/inference_vectors.npz')
    (REPORT/'getup-vectors.json').write_text(json.dumps({k:rec[k].tolist() for k in rec.files}),encoding='utf-8')
    report={'passed':True,'observations':len(obs),'max_errors':errors,
            'clanker_source_sha256':sha(LOCO/'model.pt'),'clanker_onnx_sha256':sha(path),
            'getup_onnx_sha256':sha(recovery_path),'scope':'ONNX/PyTorch parity, not physical transfer'}
    (REPORT/'export-parity.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
