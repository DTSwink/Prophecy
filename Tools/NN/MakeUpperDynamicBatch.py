"""Make batch-dynamic copies of the installed upper MLPs; preserve frozen originals."""
import json
from pathlib import Path
import numpy as np
import onnx
from onnx.reference import ReferenceEvaluator
root=Path(__file__).resolve().parents[2]
results=[]
for source in sorted((root/'Content/locomotion/NN').rglob('prophecy_upper_body_b100.onnx')):
    model=onnx.load(source)
    # These row-wise MLP operations contain no fixed-batch reshape or cross-row reduction.
    assert {node.op_type for node in model.graph.node}<={'Constant','Mul','Gemm','LayerNormalization','Div','Erf','Add'}
    for value in list(model.graph.input)+list(model.graph.output)+list(model.graph.value_info):
        dims=value.type.tensor_type.shape.dim
        if dims and dims[0].dim_value==100:
            dims[0].ClearField('dim_value');dims[0].dim_param='batch'
    onnx.checker.check_model(model)
    target=source.with_name('prophecy_upper_body_dynamic.onnx')
    onnx.save(model,target)
    fixed=ReferenceEvaluator(onnx.load(source))
    dynamic=ReferenceEvaluator(model)
    data=np.random.default_rng(42).normal(size=(100,281)).astype(np.float32)
    expected=fixed.run(None,{model.graph.input[0].name:data})[0]
    maximum=0.
    for count in (1,2,3,100):
        actual=dynamic.run(None,{model.graph.input[0].name:data[:count]})[0]
        maximum=max(maximum,float(np.max(np.abs(actual-expected[:count]))))
    assert maximum<1.e-5,(source,maximum)
    results.append({'source':str(source.relative_to(root)),'dynamic':str(target.relative_to(root)),
                    'batches':[1,2,3,100],'maximum_error':maximum})
out=root/'Saved/FKReturn/feedback-fix/dynamic-models.json'
out.write_text(json.dumps(results,indent=2))
print(json.dumps(results))
