import json,numpy as np,onnx
from onnx.reference import ReferenceEvaluator
from pathlib import Path
p=Path('Saved/Diagnostics/Head24520261003')
rows=[r for r in map(json.loads,(p/'return_baseline-inputs.jsonl').read_text().splitlines()) if r['actor']=='BP_ProphecyManualPoseAgent_C_0']
e=ReferenceEvaluator(onnx.load('Content/locomotion/NN/prophecy_upper_body_dynamic.onnx'))
x=np.array([r['upper_input'] for r in rows],dtype=np.float32);y=e.run(None,{e.input_names[0]:x})[0];expected=np.array([r['upper_delta'] for r in rows]);print('model parity',np.max(np.abs(y-expected)))
