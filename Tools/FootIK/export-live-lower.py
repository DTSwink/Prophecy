"""Probe-only lower forecasting graph for horizontal live terrain publication.

The existing lower FK already supplies the authoritative pelvis and both legs
in the full graph. Reuse that exact branch; upper placeholders must never be
published without liveJoin's actual game upper pose. No Content writes.
"""
import os, sys, json, copy, hashlib, time, argparse, importlib.util, threading
from pathlib import Path
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[key]='1'
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/Diagnostics/FootIKPort20261030';MODELS=ROOT/'Content/FootIKLab/NN'
sys.path.insert(0,str(ROOT/'Saved/Diagnostics/BodyflipPort20261030/python'))
import numpy as np
import onnx,onnxruntime as ort
LOWER_NAMES=['pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r']
def digest(b):return hashlib.sha256(b).hexdigest()
def constants(model):
    result={v.name:onnx.numpy_helper.to_array(v) for v in model.graph.initializer}
    for n in model.graph.node:
        if n.op_type=='Constant':
            for a in n.attribute:
                if a.name=='value':result[n.output[0]]=onnx.numpy_helper.to_array(a.t)
    return result

def lower_graph(model,bank):
    result=copy.deepcopy(model);p={v:n for n in result.graph.node for v in n.output};c=constants(result)
    final=p[result.graph.output[0].name]
    if final.op_type!='Concat' or len(final.input)!=12:raise ValueError('Unrecognized full forecast output contract')
    state=p[final.input[0]]
    if state.op_type!='Split' or len(state.output)!=7:raise ValueError('Unrecognized recurrent state layout')
    original_final=list(final.input)
    position_reshape,rotation_reshape=(p[final.input[i]] for i in (8,9))
    if position_reshape.op_type!='Reshape' or rotation_reshape.op_type!='Reshape':raise ValueError('Pose output layout changed')
    position_transform,rotation_transform=p[position_reshape.input[0]],p[rotation_reshape.input[0]]
    if position_transform.op_type!='MatMul' or rotation_transform.op_type!='MatMul':raise ValueError('Missing course-axis conversion')
    position_add=p[position_transform.input[0]]
    if position_add.op_type!='Add':raise ValueError('Missing origin translation')
    expected=[bank['names'].index(name) for name in LOWER_NAMES]
    def lower_input(endpoint):
        sources=[];indices=[];value=endpoint
        while p[value].op_type=='ScatterND':
            n=p[value];update=p[n.input[2]]
            if update.op_type!='Reshape':raise ValueError('Changed lower overlay update')
            update=p[update.input[0]]
            if update.op_type!='Expand':raise ValueError('Changed lower overlay expansion')
            update=p[update.input[0]]
            if update.op_type!='Gather':raise ValueError('Changed lower overlay selection')
            axis=next((a.i for a in update.attribute if a.name=='axis'),0)
            if axis!=1:raise ValueError('Lower overlay is not indexed by bone')
            sources.append(update.input[0]);indices.append(int(c[update.input[1]]));value=n.input[0]
        if len(sources)!=9 or len(set(sources))!=1 or list(reversed(indices))!=expected:
            raise ValueError('Lower decoder does not supply precisely pelvis and both full legs')
        return sources[0]
    lower_positions=lower_input(position_add.input[0]);lower_rotations=lower_input(rotation_transform.input[0])
    # Keep all final origin/course operations unchanged. Only choose the existing
    # lower checkpoint FK instead of its nine-copy overlay into the upper FK.
    position_add.input[0]=lower_positions;rotation_transform.input[0]=lower_rotations
    # No upper predictor consumes these fields in this dedicated graph. Lower
    # recurrence remains exactly current->previous plus the new lower result.
    final.input[3]=state.output[3];final.input[6]=state.output[6]
    needed=set()
    def nested_external(g):
        local={v.name for v in g.input}|{v.name for v in g.initializer}|{v for n in g.node for v in n.output}
        for n in g.node:
            for v in n.input:
                if v and v not in local:yield v
            for a in n.attribute:
                if a.type==onnx.AttributeProto.GRAPH:yield from nested_external(a.g)
                elif a.type==onnx.AttributeProto.GRAPHS:
                    for sub in a.graphs:yield from nested_external(sub)
    def visit(v):
        if not v or v in needed:return
        needed.add(v)
        if v not in p:return
        n=p[v]
        for i in n.input:visit(i)
        for a in n.attribute:
            if a.type==onnx.AttributeProto.GRAPH:
                for i in nested_external(a.g):visit(i)
            elif a.type==onnx.AttributeProto.GRAPHS:
                for sub in a.graphs:
                    for i in nested_external(sub):visit(i)
    for v in result.graph.output:visit(v.name)
    nodes=[n for n in result.graph.node if any(v in needed for v in n.output)]
    init=[v for v in result.graph.initializer if v.name in needed];values=[v for v in result.graph.value_info if v.name in needed]
    result.graph.ClearField('node');result.graph.node.extend(nodes)
    result.graph.ClearField('initializer');result.graph.initializer.extend(init)
    result.graph.ClearField('value_info');result.graph.value_info.extend(values)
    original_p={n.name:n for n in model.graph.node};changed={final.name,position_add.name,rotation_transform.name}
    for n in nodes:
        if n.name not in changed and n.SerializeToString()!=original_p[n.name].SerializeToString():raise ValueError('Changed original computation outside the explicit output selectors')
    original_i={v.name:v for v in model.graph.initializer}
    if any(v.SerializeToString()!=original_i[v.name].SerializeToString() for v in init):raise ValueError('Changed a retained model weight')
    # The retained numerical lower branch must not read an upper state, even
    # though inert passthrough output fields retain the 413/710 native layout.
    lower_dependencies=set()
    def visit_lower(v):
        if not v or v in lower_dependencies:return
        lower_dependencies.add(v)
        if v not in p:return
        n=p[v]
        if n is state:return
        for x in n.input:visit_lower(x)
        for a in n.attribute:
            if a.type==onnx.AttributeProto.GRAPH:
                for x in nested_external(a.g):visit_lower(x)
    for v in (lower_positions,lower_rotations,original_final[1],original_final[5],original_final[7],original_final[10],original_final[11]):visit_lower(v)
    forbidden=set(state.output[2:4])|{state.output[4],state.output[5],state.output[6]}
    if lower_dependencies&forbidden:raise ValueError('Lower numerical branch reads upper state '+str(lower_dependencies&forbidden))
    onnx.checker.check_model(result)
    return result,dict(nodesBefore=len(model.graph.node),nodesAfter=len(nodes),initializerBytesBefore=sum(len(v.raw_data) for v in model.graph.initializer),initializerBytesAfter=sum(len(v.raw_data) for v in init),
        authoritativeBones=LOWER_NAMES,lowerIndices=expected,lowerDependsOnlyOnPreviousCurrentLower=True,retainedWeightsUnchanged=True,
        upperState='Inert current/base passthrough; never authoritative',upperPose='Existing lower-checkpoint neutral FK; publication must use actual manager upper',selectors=list(changed))

def load_helpers():
    spec=importlib.util.spec_from_file_location('shape_helpers',ROOT/'Tools/FootIK/annotate-nn-shapes.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper);return helper

def prove(direction,write_sequences=False):
    timer=threading.Timer(110,lambda:os._exit(124));timer.daemon=True;timer.start()
    path=MODELS/f'run-{direction}-resume.onnx';data=path.read_bytes();model=onnx.load_from_string(data);bank=json.loads((MODELS/f'run-{direction}-seed.json').read_text())
    candidate,report=lower_graph(model,bank);candidate_data=candidate.SerializeToString();candidate_path=OUT/f'run-{direction}-live-lower-candidate.onnx';candidate_path.write_bytes(candidate_data)
    print(json.dumps(dict(stage='lower-candidate',**report,bytes=len(candidate_data))),flush=True)
    helper=load_helpers();sessions=[];init=[]
    for value in (data,candidate_data):
        c=time.process_time();t=time.perf_counter();sessions.append(helper.session(value));init.append(dict(cpuMs=(time.process_time()-c)*1000,wallMs=(time.perf_counter()-t)*1000))
    encoder=helper.session((MODELS/f'run-{direction}-seed.onnx').read_bytes())
    indices=list(range(82))+list(range(262,280))+list(range(370,373))+list(range(673,710))
    for j in report['lowerIndices']:indices.extend(range(373+j*3,376+j*3));indices.extend(range(448+j*9,457+j*9))
    indices=np.asarray(sorted(indices),np.int64);frames=0;measured=0;cpu=[0.,0.];wall=[0.,0.];sequences=[]
    mismatch=None
    for course,(roots,yaws) in enumerate(helper.courses(bank)):
        encoded=encoder.run(None,{'input':helper.seed_input(bank,roots,yaws,True)})[0];states=[encoded[0,:370].copy(),encoded[0,:370].copy()];origin=encoded[0,370:373];rows=[[],[]]
        for k in range(72):
            values=[None,None]
            for j in (frames%2,1-frames%2):
                packed=np.concatenate((states[j],roots[k:k+10].ravel(),yaws[k:k+10],origin))[None]
                c=time.process_time();t=time.perf_counter();values[j]=sessions[j].run(None,{'input':packed})[0]
                if k>=4:cpu[j]+=time.process_time()-c;wall[j]+=time.perf_counter()-t
                states[j]=values[j][0,:370].copy()
                if write_sequences:rows[j].append(values[j][0,370:].tolist())
            a,b=(v[0,indices] for v in values)
            if not np.array_equal(a.view(np.uint32),b.view(np.uint32)):
                mismatch=dict(course=course,frame=k,maxAbs=float(np.max(np.abs(a-b))),mismatchedFloat32=int(np.count_nonzero(a.view(np.uint32)!=b.view(np.uint32))));break
            if not all(np.isfinite(v).all() for v in values):raise RuntimeError('Nonfinite placeholder pose')
            frames+=1;measured+=int(k>=4)
        sequences.append(dict(roots=roots.tolist(),yaw=yaws.tolist(),full=rows[0],lower=rows[1]))
        if mismatch:break
    report.update(scope='Candidate only for horizontal LIVE publication; full graphs remain unchanged',direction=direction,ort=ort.__version__,contentSha256=digest(data),candidateSha256=digest(candidate_data),candidateBytes=len(candidate_data),exactFrames=frames,exactFloat32Values=frames*len(indices),authoritativeIndices=indices.tolist(),mismatch=mismatch,sessionInit=init,
        baselineCpuMs=cpu[0]*1000/max(1,measured),candidateCpuMs=cpu[1]*1000/max(1,measured),baselineWallMs=wall[0]*1000/max(1,measured),candidateWallMs=wall[1]*1000/max(1,measured),contentUnchanged=path.read_bytes()==data)
    (OUT/f'nn-live-lower-{direction}-proof.json').write_text(json.dumps(report,indent=2)+'\n')
    if write_sequences:(OUT/f'nn-live-lower-{direction}-sequences.json').write_text(json.dumps(dict(names=bank['names'],seeds=bank['seeds'],courses=sequences),separators=(',',':'))+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='authoritativeIndices'}),flush=True)
    if mismatch:raise RuntimeError('Lower authoritative recurrence changed')

def stage_approved():
    # Explicit opt-in, used only after reviewing the independent recurrence and
    # final publication proofs. Full seed/step/resume graphs are never replaced.
    proof=json.loads((OUT/'nn-live-lower-forward-proof.json').read_text());publication=json.loads((OUT/'live-lower-publication.json').read_text())
    source=(MODELS/'run-forward-resume.onnx').read_bytes();candidate_path=OUT/'run-forward-live-lower-candidate.onnx'
    # A verified duplicate can be removed after staging to keep the laptop's
    # temporary storage small. Revalidating that same staged graph is safe.
    if not candidate_path.exists():candidate_path=MODELS/'run-forward-live-lower-resume.onnx'
    data=candidate_path.read_bytes()
    if proof.get('mismatch') is not None or proof.get('exactFrames')!=216 or not publication.get('passed') or publication.get('completePublishedFrames')!=864 or publication.get('materialPinFrames',0)<1:
        raise ValueError('The reviewed recurrence and complete-pose publication proofs are incomplete')
    if digest(source)!=proof['contentSha256'] or digest(data)!=proof['candidateSha256']:raise ValueError('Verified graph fingerprints changed')
    original_receipt=json.loads((MODELS/'Receipt.json').read_text())
    if original_receipt['resumeGraphs']['forward']['sha256']['run-forward-resume.onnx']!=digest(source):raise ValueError('Original graph receipt changed')
    receipt=dict(schema=1,scope='live-horizontal-forward',model='run-forward-live-lower-resume.onnx',sourceModel='run-forward-resume.onnx',
        sourceSha256=digest(source),sourceSha1=hashlib.sha1(source).hexdigest(),sha256=digest(data),sha1=hashlib.sha1(data).hexdigest(),bytes=len(data),inputWidth=413,outputWidth=710,
        authoritativeBones=LOWER_NAMES,upperPose='Lower-checkpoint neutral FK placeholders; only actual game upper may be published',
        exactRecurrentFrames=proof['exactFrames'],exactAuthoritativeFloat32Values=proof['exactFloat32Values'],publishedFrames=publication['completePublishedFrames'],publishedPinFrames=publication['materialPinFrames'],
        maxPublishedPositionM=publication['maxPositionM'],maxPublishedQuaternionComponent=publication['maxQuaternionComponent'],maxPublishedFootReceiptNumber=publication['maxFootReceiptNumber'],
        baselineCpuMs=proof['baselineCpuMs'],candidateCpuMs=proof['candidateCpuMs'],pythonOrt=proof['ort'],nativeAcceptance='Pending actual engine ORT/gameplay tests')
    (MODELS/receipt['model']).write_bytes(data);(MODELS/'LiveLowerReceipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--direction',choices=['forward','backward','left','right'],default='forward');parser.add_argument('--sequences',action='store_true');parser.add_argument('--draft-only',action='store_true');parser.add_argument('--stage-approved',action='store_true');args=parser.parse_args()
    if args.stage_approved:stage_approved()
    elif args.draft_only:
        path=MODELS/f'run-{args.direction}-resume.onnx';model=onnx.load(path);bank=json.loads((MODELS/f'run-{args.direction}-seed.json').read_text());candidate,report=lower_graph(model,bank);print(json.dumps(dict(**report,candidateBytes=len(candidate.SerializeToString()))))
    else:prove(args.direction,args.sequences)
