"""An exported requested-action policy must retain values beyond the input cap."""
import tempfile
from pathlib import Path
import numpy as np
import torch
import onnxruntime as ort
from export_policy import PhysicalActor


class Fixture(torch.nn.Module):
    def as_onnx(self,_):return self
    def forward(self,obs):return obs[:,:2]*7


def main():
    torch.set_num_threads(1)
    options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
    with tempfile.TemporaryDirectory() as temp:
        for requested in (False,True):
            actor=PhysicalActor(Fixture(),4,preserve_requests=requested)
            path=Path(temp)/f'fixture-{requested}.onnx'
            torch.onnx.export(actor,torch.ones(1,3),str(path),dynamo=False,opset_version=17,
                input_names=['observations'],output_names=['actions'],dynamic_axes={'observations':{0:'batch'},'actions':{0:'batch'}})
            session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
            obs=np.array([[1,-1,0],[2,-2,0]],dtype=np.float32)
            result=session.run(None,{'observations':obs})[0]
            expected=obs[:,:2]*7 if requested else np.clip(obs[:,:2]*7,-4,4)
            np.testing.assert_array_equal(result,expected)
    print('PASS: ONNX retains requested actions beyond4 in the new contract and preserves historical bounded exports.')


if __name__=='__main__':main()
