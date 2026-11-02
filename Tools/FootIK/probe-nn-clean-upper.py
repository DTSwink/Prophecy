"""Saved-only exact batching probe for the exported upper rotation normalizer.

This extracts the already deployed arithmetic. It does not import Torch, load
weights into a policy session, change Content, or approximate the normalization.
"""
import os, sys, copy, json, time, hashlib, threading, collections, argparse, importlib.util
from pathlib import Path
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '1'
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'Saved/Diagnostics/FootIKPort20261030'
sys.path.insert(0, str(ROOT/'Saved/Diagnostics/BodyflipPort20261030/python'))
import numpy as np
import onnx, onnxruntime as ort

def digest(b): return hashlib.sha256(b).hexdigest()
def producers(model): return {o:n for n in model.graph.node for o in n.output}
def constants(model):
    result = {v.name:onnx.numpy_helper.to_array(v) for v in model.graph.initializer}
    for node in model.graph.node:
        if node.op_type == 'Constant':
            for a in node.attribute:
                if a.name == 'value': result[node.output[0]] = onnx.numpy_helper.to_array(a.t)
    return result

def extract(model, input_name, output_name, shape_in, shape_out):
    p = producers(model); included = set(); needed_init = set()
    initializers = {v.name:v for v in model.graph.initializer}
    def visit(v):
        if not v or v == input_name or v in included: return
        included.add(v)
        if v in initializers: needed_init.add(v); return
        if v not in p: raise ValueError('Unexpected external value '+v)
        n = p[v]
        if any(a.type in (onnx.AttributeProto.GRAPH, onnx.AttributeProto.GRAPHS) for a in n.attribute):
            raise ValueError('Normalizer unexpectedly contains control flow')
        for i in n.input: visit(i)
    visit(output_name)
    nodes = [copy.deepcopy(n) for n in model.graph.node if any(o in included for o in n.output)]
    graph = onnx.helper.make_graph(nodes, 'exact-clean-upper',
        [onnx.helper.make_tensor_value_info(input_name, onnx.TensorProto.FLOAT, shape_in)],
        [onnx.helper.make_tensor_value_info(output_name, onnx.TensorProto.FLOAT, shape_out)],
        [copy.deepcopy(initializers[n]) for n in needed_init])
    result = onnx.helper.make_model(graph, opset_imports=model.opset_import)
    result.ir_version = model.ir_version
    onnx.checker.check_model(result)
    return result

def candidates(model):
    p = producers(model); c = constants(model); found = []
    def types(n): return [p[x].op_type if x in p else None for x in n.input]
    for n in model.graph.node:
        if n.op_type != 'Concat' or types(n) != ['Reshape','Slice','Reshape','Reshape','Slice','Reshape','Reshape']: continue
        first, left, right = p[n.input[0]], p[n.input[1]], p[n.input[4]]
        if left.input[0] != right.input[0] or c.get(first.input[1], np.array([])).tolist() != [1,60]: continue
        if [c.get(left.input[k], np.array([])).tolist() for k in (1,2,3)] != [[60],[63],[1]]: continue
        if [c.get(right.input[k], np.array([])).tolist() for k in (1,2,3)] != [[75],[78],[1]]: continue
        found.append((n, left.input[0]))
    return found

def batched(model, node, input_name):
    p = producers(model); c = constants(model)
    # Retain precisely the first branch's row-wise normalization arithmetic.
    # Its Shape nodes already support arbitrary batch length; only the two
    # outer layout operations belonged to the original ten-rotation grouping.
    normalized_output = p[node.input[0]].input[0]
    subset = extract(model, input_name, normalized_output, [1,90], [10,6])
    reshape_inputs = []
    for n in subset.graph.node:
        if n.op_type == 'Reshape' and c.get(n.input[1], np.array([])).tolist() == [-1,6]:
            s = p.get(n.input[0])
            if s is not None and s.op_type == 'Slice' and s.input[0] == input_name:
                if [c.get(s.input[k], np.array([])).tolist() for k in (1,2,3)] == [[0],[60],[1]]:
                    reshape_inputs.append(n.output[0])
    if len(reshape_inputs) != 1: raise ValueError('Core rotation input was not identified uniquely')
    normalized_input = reshape_inputs[0]
    core = extract(model, normalized_input, normalized_output, [14,6], [14,6])
    nodes = []; init = list(core.graph.initializer)
    prefix = '__footik_batch_clean_'
    def tensor(name, values):
        full = prefix+name; init.append(onnx.numpy_helper.from_array(np.asarray(values,np.int64), full)); return full
    indices = list(range(60))+list(range(63,75))+list(range(78,90))
    gather = prefix+'rotations'; nodes.append(onnx.helper.make_node('Gather',[input_name,tensor('indices',indices)],[gather],axis=1))
    nodes.append(onnx.helper.make_node('Reshape',[gather,tensor('shape',[14,6])],[normalized_input]))
    nodes.extend(core.graph.node)
    flat = prefix+'flat'; nodes.append(onnx.helper.make_node('Reshape',[normalized_output,tensor('flat_shape',[1,84])],[flat]))
    pos = prefix+'positions'; nodes.append(onnx.helper.make_node('Gather',[input_name,tensor('positions_idx',[60,61,62,75,76,77])],[pos],axis=1))
    all_values = prefix+'values'; nodes.append(onnx.helper.make_node('Concat',[flat,pos],[all_values],axis=1))
    order = list(range(60))+[84,85,86]+list(range(60,72))+[87,88,89]+list(range(72,84))
    nodes.append(onnx.helper.make_node('Gather',[all_values,tensor('output_order',order)],list(node.output),axis=1))
    graph = onnx.helper.make_graph(nodes,'batched-clean-upper',
        [onnx.helper.make_tensor_value_info(input_name,onnx.TensorProto.FLOAT,[1,90])],
        [onnx.helper.make_tensor_value_info(node.output[0],onnx.TensorProto.FLOAT,[1,90])],init)
    result = onnx.helper.make_model(graph,opset_imports=model.opset_import);result.ir_version=model.ir_version
    onnx.checker.check_model(result)
    return result

def session(model):
    options = ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
    options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
    options.add_session_config_entry('session.intra_op.allow_spinning','0')
    options.add_session_config_entry('session.inter_op.allow_spinning','0')
    return ort.InferenceSession(model.SerializeToString(),options,providers=['CPUExecutionProvider'])

def full_candidate(model):
    replacements={};extra=[];allowed_removed=set()
    for index,(node,input_name) in enumerate(candidates(model)):
        original=extract(model,input_name,node.output[0],[1,90],[1,90])
        allowed_removed.update(n.name for n in original.graph.node)
        part=batched(model,node,input_name);prefix=f'__footikCleanBatch{index}_'
        names={v:prefix+v for n in part.graph.node for v in n.output}
        names.update({i.name:prefix+i.name for i in part.graph.initializer})
        names[input_name]=input_name;names[node.output[0]]=node.output[0]
        nodes=[]
        for n in part.graph.node:
            n=copy.deepcopy(n);n.name=prefix+n.name
            n.input[:]=[names.get(v,v) for v in n.input];n.output[:]=[names.get(v,v) for v in n.output];nodes.append(n)
        for v in part.graph.initializer:
            v=copy.deepcopy(v);v.name=names[v.name];extra.append(v)
        replacements[node.name]=nodes
    candidate=copy.deepcopy(model);candidate.graph.ClearField('node')
    for n in model.graph.node:candidate.graph.node.extend(replacements.get(n.name,[copy.deepcopy(n)]))
    candidate.graph.initializer.extend(extra)
    p=producers(candidate);needed=set()
    def subgraph_refs(g):
        local={i.name for i in g.input}|{i.name for i in g.initializer}|{v for n in g.node for v in n.output}
        for n in g.node:
            for v in n.input:
                if v and v not in local:yield v
            for a in n.attribute:
                if a.type==onnx.AttributeProto.GRAPH:yield from subgraph_refs(a.g)
                elif a.type==onnx.AttributeProto.GRAPHS:
                    for sub in a.graphs:yield from subgraph_refs(sub)
    def visit(v):
        if not v or v in needed:return
        needed.add(v)
        if v not in p:return
        n=p[v]
        for i in n.input:visit(i)
        for a in n.attribute:
            if a.type==onnx.AttributeProto.GRAPH:
                for i in subgraph_refs(a.g):visit(i)
            elif a.type==onnx.AttributeProto.GRAPHS:
                for sub in a.graphs:
                    for i in subgraph_refs(sub):visit(i)
    for v in candidate.graph.output:visit(v.name)
    kept=[n for n in candidate.graph.node if any(v in needed for v in n.output)]
    candidate.graph.ClearField('node');candidate.graph.node.extend(kept)
    values=[v for v in candidate.graph.value_info if v.name in needed]
    candidate.graph.ClearField('value_info');candidate.graph.value_info.extend(values)
    kept_original={n.name:n for n in kept if not n.name.startswith('__footikCleanBatch')}
    removed=[n for n in model.graph.node if n.name not in kept_original]
    unexpected=[n.name for n in removed if n.name not in allowed_removed and n.name not in replacements]
    if unexpected:raise RuntimeError('Removed nodes outside verified cleanup subgraphs: '+str(unexpected[:10]))
    for n in model.graph.node:
        if n.name in kept_original and n.SerializeToString()!=kept_original[n.name].SerializeToString():raise RuntimeError('Changed unrelated arithmetic '+n.name)
    if any(a.SerializeToString()!=b.SerializeToString() for a,b in zip(model.graph.initializer,candidate.graph.initializer)):
        raise RuntimeError('Original weights changed')
    candidate=onnx.shape_inference.infer_shapes(candidate,strict_mode=True,data_prop=True)
    onnx.checker.check_model(candidate)
    return candidate,dict(replacements=len(replacements),nodesBefore=len(model.graph.node),nodesAfter=len(candidate.graph.node),originalWeightsUnchanged=True,unrelatedArithmeticUnchanged=True)

def full_proof():
    timer=threading.Timer(100,lambda:os._exit(124));timer.daemon=True;timer.start()
    path=ROOT/'Content/FootIKLab/NN/run-forward-resume.onnx';data=path.read_bytes();model=onnx.load_from_string(data)
    new,report=full_candidate(model);serialized=new.SerializeToString()
    candidate_path=OUT/'run-forward-resume-clean-batched-candidate.onnx';candidate_path.write_bytes(serialized)
    print(json.dumps(dict(stage='candidate',**report,bytes=len(serialized))),flush=True)
    spec=importlib.util.spec_from_file_location('shape_helpers',ROOT/'Tools/FootIK/annotate-nn-shapes.py');helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
    sessions=[];init=[]
    for graph in (model,new):
        c=time.process_time();t=time.perf_counter();sessions.append(session(graph));init.append(dict(cpuMs=(time.process_time()-c)*1000,wallMs=(time.perf_counter()-t)*1000))
    encoder=helpers.session((ROOT/'Content/FootIKLab/NN/run-forward-seed.onnx').read_bytes())
    bank=json.loads((ROOT/'Content/FootIKLab/NN/run-forward-seed.json').read_text());frames=0;measured=0;cpu=[0.,0.];wall=[0.,0.];mismatch=None
    for course,(roots,yaws) in enumerate(helpers.courses(bank)):
        encoded=encoder.run(None,{'input':helpers.seed_input(bank,roots,yaws,True)})[0];state=encoded[0,:370];origin=encoded[0,370:373]
        for k in range(72):
            x=np.concatenate((state,roots[k:k+10].ravel(),yaws[k:k+10],origin))[None];output=[None,None]
            for j in (frames%2,1-frames%2):
                c=time.process_time();t=time.perf_counter();output[j]=sessions[j].run(None,{'input':x})[0]
                if k>=4:cpu[j]+=time.process_time()-c;wall[j]+=time.perf_counter()-t
            a,b=output
            if not np.array_equal(a.view(np.uint32),b.view(np.uint32)):
                mismatch=dict(course=course,frame=k,maxAbs=float(np.max(np.abs(a-b))),mismatchedFloat32=int(np.count_nonzero(a.view(np.uint32)!=b.view(np.uint32))));break
            state=a[0,:370];frames+=1;measured+=int(k>=4)
        if mismatch:break
    report.update(scope='Saved-only full resume graph; no deployed change',ort=ort.__version__,contentSha256=digest(data),candidateSha256=digest(serialized),candidateBytes=len(serialized),
        exactFrames=frames,exactFloat32Values=frames*710,mismatch=mismatch,sessionInit=init,
        baselineCpuMs=cpu[0]*1000/max(1,measured),candidateCpuMs=cpu[1]*1000/max(1,measured),baselineWallMs=wall[0]*1000/max(1,measured),candidateWallMs=wall[1]*1000/max(1,measured),contentUnchanged=path.read_bytes()==data)
    (OUT/'nn-clean-upper-full-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    if mismatch:raise RuntimeError('Candidate failed exact recurrent comparison')

def samples():
    random = np.random.default_rng(73491)
    for i in range(1024):
        x = random.normal(size=(1,90)).astype(np.float32)
        if i % 4 == 0: x *= np.float32(10.**random.uniform(-12,12))
        if i % 8 == 0:
            for start in (*range(0,60,6),63,69,78,84):
                x[:,start+3:start+6] = x[:,start:start+3] * np.float32(1+1e-6*(i%3-1))
        yield x
    for eps in (0.,-0.,1e-20,1e-9,1e-8,np.nextafter(np.float32(1e-8),np.float32(0)),np.nextafter(np.float32(1e-8),np.float32(1)),1.,1e12):
        for axis in range(6):
            for layout in range(4):
                x = np.zeros((1,90),np.float32)
                for start in (*range(0,60,6),63,69,78,84):
                    x[0,start+axis] = eps
                    if layout==1: x[0,start+(axis+3)%6] = eps
                    if layout==2: x[0,start+(axis+1)%6] = -eps
                    if layout==3: x[0,start+(axis+3)%6] = -eps
                yield x

def main():
    threading.Timer(60,lambda:os._exit(124)).start()
    path = ROOT/'Content/FootIKLab/NN/run-forward-resume.onnx';data=path.read_bytes();model=onnx.load_from_string(data)
    found = candidates(model)
    if len(found)!=6: raise ValueError('Expected exactly six structurally verified clean-upper invocations')
    node,input_name = found[1]
    old=extract(model,input_name,node.output[0],[1,90],[1,90]);new=batched(model,node,input_name)
    reference,candidate = session(old),session(new)
    cases=list(samples());mismatch=None
    for i,x in enumerate(cases):
        a=reference.run(None,{input_name:x})[0];b=candidate.run(None,{input_name:x})[0]
        if not np.array_equal(a.view(np.uint32),b.view(np.uint32)):
            mismatch=dict(case=i,maxAbs=float(np.max(np.abs(a-b))),mismatchedFloat32=int(np.count_nonzero(a.view(np.uint32)!=b.view(np.uint32))));break
    cpu=[0.,0.];wall=[0.,0.];runs=2048
    if mismatch is None:
        for i in range(runs):
            x=cases[i%len(cases)]
            for j in (i%2,1-i%2):
                s=(reference,candidate)[j];c=time.process_time();t=time.perf_counter();s.run(None,{input_name:x});cpu[j]+=time.process_time()-c;wall[j]+=time.perf_counter()-t
    result=dict(scope='Isolated upper cleanup only; no full policy deployment',ort=ort.__version__,contentSha256=digest(data),
        matchedInvocations=[n.name for n,_ in found],exactCases=len(cases) if mismatch is None else i,
        exactFloat32Values=len(cases)*90 if mismatch is None else 0,mismatch=mismatch,
        nodesBefore=len(old.graph.node),nodesAfter=len(new.graph.node),arithmetic='Same row-wise exported normalizer, batched from 10+1+1+1+1 to 14',
        baselineCpuUs=cpu[0]*1e6/runs,candidateCpuUs=cpu[1]*1e6/runs,baselineWallUs=wall[0]*1e6/runs,candidateWallUs=wall[1]*1e6/runs,
        contentUnchanged=path.read_bytes()==data)
    for name,g in [('clean-upper-original.onnx',old),('clean-upper-batched-candidate.onnx',new)]:
        serialized=g.SerializeToString();(OUT/name).write_bytes(serialized);result[name]=dict(bytes=len(serialized),sha256=digest(serialized))
    (OUT/'nn-clean-upper-micro-proof.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    os._exit(0 if mismatch is None else 1)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--full',action='store_true');args=parser.parse_args()
    full_proof() if args.full else main()
