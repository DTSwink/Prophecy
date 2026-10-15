"""Export a deterministic physical actor and verify CPU ONNX Runtime parity.

Does not require CUDA or start another physics simulation. Exporting a network
does not certify that it has learned recovery or transfers to Jolt.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from tensordict import TensorDict
from rsl_rl.models import MLPModel


class PhysicalActor(torch.nn.Module):
    def __init__(self,actor,bound,preserve_requests=False):
        super().__init__();self.actor=actor.as_onnx(False);self.bound=bound;self.preserve_requests=preserve_requests

    def forward(self,obs):
        actions=self.actor(obs)
        return actions if self.preserve_requests else actions.clamp(-self.bound,self.bound)


def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--output')
    a=p.parse_args();path=Path(a.checkpoint).resolve()
    output=Path(a.output) if a.output else path.with_suffix('.onnx')
    torch.set_num_threads(1);torch.manual_seed(116)
    state=torch.load(path,map_location='cpu',weights_only=False)
    env=state['infos']['physical_recovery'];cfg=json.loads((path.parent/'config.json').read_text())['ppo']
    if env['kind']!='physical_recovery_v1':raise ValueError('Not a physical-recovery checkpoint')
    width=int(state['actor_state_dict']['mlp.0.weight'].shape[1])
    count=env['controller']['action_count']
    inputs=TensorDict({'actor':torch.zeros(1,width)},batch_size=[1])
    allowed=('hidden_dims','activation','obs_normalization','distribution_cfg')
    actor=MLPModel(inputs,cfg['obs_groups'],'actor',count,
        **{k:copy.deepcopy(v) for k,v in cfg['actor'].items() if k in allowed})
    actor.load_state_dict(state['actor_state_dict']);actor.eval();bound=env['controller'].get('action_bound',1)
    preserve_requests=env.get('previous_action_observation')=='requested'
    wrapper=PhysicalActor(actor,bound,preserve_requests).eval()
    torch.onnx.export(wrapper,torch.zeros(1,width),str(output),dynamo=False,opset_version=17,
        input_names=['observations'],output_names=['actions'],
        dynamic_axes={'observations':{0:'batch'},'actions':{0:'batch'}})
    import onnxruntime as ort
    options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
    session=ort.InferenceSession(str(output),sess_options=options,providers=['CPUExecutionProvider'])
    maximum=0.
    with torch.inference_mode():
        for batch in (1,7,64):
            obs=torch.randn(batch,width)*2
            expected=actor(TensorDict({'actor':obs},batch_size=[batch]))
            if not preserve_requests:expected=expected.clamp(-bound,bound)
            expected=expected.numpy()
            actual=session.run(None,{'observations':obs.numpy()})[0]
            maximum=max(maximum,float(np.abs(expected-actual).max()))
            np.testing.assert_allclose(expected,actual,atol=2e-5,rtol=2e-5)
    report={'passed':True,'checkpoint':str(path),'checkpoint_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'onnx_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'input_width':width,'output_width':count,
        'max_absolute_error':maximum,'tested_batches':[1,7,64],'physical_recovery':env,
        'output_semantics':'Raw requests: retain for next observation; clamp to controller action_bound before physical actuation' if preserve_requests else 'Bounded applied actions',
        'scope':'Deterministic inference parity only; no learned recovery or Jolt transfer certification'}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='physical_recovery'},indent=2))


if __name__=='__main__':main()
