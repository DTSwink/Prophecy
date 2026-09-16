"""Export only the saved defense networks, then check every saved neural trace.

No training import, model re-training, geometry changes, or authored assets.
Successful neural parity is a prerequisite, not proof of full rollout parity.
"""
from pathlib import Path
import hashlib, json, sys
import numpy as np
import onnx
from onnx import helper as H, numpy_helper as N, TensorProto as T

PROJECT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT/'Saved/SlashPythonDependencies'))
import onnxruntime as ort
SOURCES = Path(r'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/saved_defense_checkpoints')
DEST = PROJECT/'Saved/DefenseIntegration/Models'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def export(weights, prefix, final, path):
    nodes=[];initializers=[]
    def constant(name,value):
        initializers.append(N.from_array(np.asarray(value,dtype=np.float32),name))
        return name
    for key in weights.files:
        if key.startswith(prefix+'.'):
            initializers.append(N.from_array(np.asarray(weights[key],dtype=np.float32),key))
    sqrt2=constant('sqrt2',np.sqrt(2.));half=constant('half',.5);one=constant('one',1.)
    current='input'
    for i in (0,3):
        stem=f'hidden_{i}'
        nodes.append(H.make_node('Gemm',[current,f'{prefix}.{i}.weight',f'{prefix}.{i}.bias'],[stem],transB=1))
        normalized=stem+'_norm'
        nodes.append(H.make_node('LayerNormalization',[stem,f'{prefix}.{i+1}.weight',f'{prefix}.{i+1}.bias'],[normalized],axis=-1,epsilon=1e-5))
        nodes.append(H.make_node('Div',[normalized,sqrt2],[stem+'_scaled']))
        nodes.append(H.make_node('Erf',[stem+'_scaled'],[stem+'_erf']))
        nodes.append(H.make_node('Add',[stem+'_erf',one],[stem+'_plus']))
        nodes.append(H.make_node('Mul',[normalized,half],[stem+'_half']))
        current=stem+'_gelu'
        nodes.append(H.make_node('Mul',[stem+'_half',stem+'_plus'],[current]))
    for key in (final+'.weight',final+'.bias'):
        if not key.startswith(prefix+'.'):
            initializers.append(N.from_array(np.asarray(weights[key],dtype=np.float32),key))
    nodes.append(H.make_node('Gemm',[current,final+'.weight',final+'.bias'],['output'],transB=1))
    width=weights[prefix+'.0.weight'].shape[1];out=weights[final+'.weight'].shape[0]
    graph=H.make_graph(nodes,path.stem,[H.make_tensor_value_info('input',T.FLOAT,['agents',width])],
                      [H.make_tensor_value_info('output',T.FLOAT,['agents',out])],initializer=initializers)
    model=H.make_model(graph,opset_imports=[H.make_opsetid('',18)],producer_name='Prophecy saved defense network export',ir_version=8)
    onnx.checker.check_model(model);onnx.save(model,path)
    return width,out

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    report={'schema':1,'neural_parity_only':True,'models':{}}
    audit={}
    configs=[('dodge','dodge_unreal_reference/reference','upper','upper.trunk','upper.delta_head','upper/input/0','upper/output/0'),
             ('dodge','dodge_unreal_reference/reference','walk','frozen.models.walk.net','frozen.models.walk.net.6','walk/input/0','walk/output'),
             ('dodge','dodge_unreal_reference/reference','run','frozen.models.run.net','frozen.models.run.net.6','run/input/0','run/output'),
             ('parry','parry_unreal_reference_770015','upper','upper.trunk','upper.delta_head','network/input','network/output')]
    for kind,directory,name,prefix,final,input_suffix,output_suffix in configs:
        source=SOURCES/directory
        with np.load(source/'weights.npz') as weights,np.load(source/'trace.npz') as trace:
            path=DEST/f'prophecy_{kind}_{name}.onnx'
            width,out=export(weights,prefix,final,path)
            options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
            session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
            rows=[];errors=[]
            for key in sorted(trace.files):
                if not key.endswith('/'+input_suffix):continue
                output_key=key[:-len(input_suffix)]+output_suffix
                x=np.asarray(trace[key],dtype=np.float32);expected=np.asarray(trace[output_key],dtype=np.float32)
                actual=session.run(None,{'input':x})[0]
                np.testing.assert_allclose(actual,expected,atol=1e-5,rtol=1e-5,err_msg=key)
                errors.append(float(np.max(np.abs(actual-expected))))
                rows.append({'key':key,'input':x.tolist(),'expected':expected.tolist()})
            assert rows, (kind,name,'no reference network calls')
            model_name=f'{kind}_{name}'
            report['models'][model_name]={'file':path.name,'sha256':digest(path),'source_weights_sha256':digest(source/'weights.npz'),
                'input_dim':int(width),'output_dim':int(out),'reference_calls':len(rows),'max_abs_error':max(errors)}
            audit[model_name]=rows
    (DEST/'networks.json').write_text(json.dumps(report,indent=2)+'\n')
    (DEST/'neural_reference.json').write_text(json.dumps(audit)+'\n')
    feature_rows=[];rebases=[];carries=[]
    with np.load(SOURCES/'parry_unreal_reference_770015/trace.npz') as trace:
        for key in sorted(trace.files):
            if '/held_target_' in key and key.endswith('/output/0'):
                prefix=key[:-len('output/0')]
                rebases.append({'key':key,'args':[trace[prefix+f'input/{i}'].reshape(-1).tolist() for i in (0,1,3,4,5,6)],
                    'expected':[trace[prefix+f'output/{i}'].reshape(-1).tolist() for i in (0,1)]})
            if key.endswith('/carry/output'):
                prefix=key[:-len('output')]
                carries.append({'key':key,'args':[trace[prefix+f'input/{i}'].reshape(-1).tolist() for i in range(3)],
                    'expected':trace[key].reshape(-1).tolist()})
            if not key.endswith('/conditioning/output'):continue
            prefix=key[:-len('output')]
            feature_rows.append({'key':key,'args':[trace[prefix+f'input/{i}'].reshape(-1).tolist() for i in range(11)],
                'expected':trace[key].reshape(-1).tolist()})
    assert feature_rows
    (DEST/'feature_reference.json').write_text(json.dumps(feature_rows)+'\n')
    assert rebases and carries
    (DEST/'state_reference.json').write_text(json.dumps({'rebases':rebases,'carries':carries})+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
