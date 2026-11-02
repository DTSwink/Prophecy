"""Bounded retained-state comparison at the first native/canonical NN fork.

Reads the captured actual game requests. No solver, editor, or training process.
Keeps one CPU thread and writes the exact pre-fork tensors for a follow-up probe.
"""
import argparse, importlib.util, json, time
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('footik_export',HERE/'export-nn.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
OUT=m.PROJECT/'Saved/Diagnostics/FootIKPort20261030'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def session(p):
    options=m.ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
    options.add_session_config_entry('session.intra_op.allow_spinning','0');options.add_session_config_entry('session.inter_op.allow_spinning','0')
    return m.ort.InferenceSession(str(p),options,providers=['CPUExecutionProvider'])
def state_of(stream):
    return m.torch.cat([getattr(stream,key) for key in ('previous','current','prev_upper','cur_upper','prev_pelvis','cur_pelvis','base')],-1)
def maxdiff(a,b):
    d=np.abs(np.asarray(a)-np.asarray(b));i=int(d.argmax())
    return dict(maximum=float(d.flat[i]),index=i,actual=float(np.asarray(a).flat[i]),expected=float(np.asarray(b).flat[i]))

@m.inference_execution()
def main(case,stop):
    records=[json.loads(line) for line in (OUT/'native-nn-captures'/(case+'-recorded-source.nn.jsonl')).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    request=records[0]['request'];direction=request.get('direction','forward')
    owner=m.ResumeLocomotion('run');m.configure_direction(owner,'run',direction);owner.runtime.install_policy()
    stream=m.Stream(owner);eager=m.Step(owner).eval()
    stem='run-'+direction;print('Creating private ORT sessions',flush=True)
    encoder=session(m.OUT/(stem+'-seed.onnx'));step=session(m.OUT/(stem+'-step.onnx'))
    print('Sessions ready',flush=True);state=None;report=[]
    expected=read(OUT/(case+'.input.json'))['policySteps']
    for i,record in enumerate(records[:stop+1]):
        request=record['request'];window=m.pack_window(request)
        if state is None or request.get('reset'):
            state=encoder.run(None,{'input':m.pack_seed(request['seeds'],request).numpy()})[0][:,:370]
        packed=np.concatenate((state,window.numpy(),np.zeros((1,3),np.float32)),-1)
        before=state_of(stream).numpy().copy() if stream.initialized else None
        actual=step.run(None,{'input':packed})[0];response=stream.step(request)
        canonical=state_of(stream).numpy();state=actual[:,:370]
        got_points=actual[:,370:448].reshape(26,3);got_axes=np.concatenate((np.eye(3,dtype=np.float32)[None],actual[:,448:673].reshape(25,3,3)),0)
        row=dict(index=i,state=maxdiff(state,canonical),points=maxdiff(got_points,response['pose']['points']),axes=maxdiff(got_axes,response['pose']['axes']),pins=maxdiff(actual[:,673:675],response['pins']),nativePoints=maxdiff(got_points,record['response']['pose']['points']),oraclePoints=maxdiff(response['pose']['points'],expected[i]['pose']['points']))
        if i>=stop-3:
            own_eager=eager(m.torch.from_numpy(packed)).numpy()
            row['sameInputEager']=maxdiff(actual,own_eager)
            if before is not None:
                canonical_packed=np.concatenate((before,window.numpy(),np.zeros((1,3),np.float32)),-1)
                same_canonical=step.run(None,{'input':canonical_packed})[0]
                row['canonicalStateOrt']=maxdiff(same_canonical[:,:370],canonical)
                np.savez_compressed(OUT/(case+f'-fork-{i}.npz'),packed=packed,canonical_packed=canonical_packed,actual=actual,own_eager=own_eager,canonical=canonical,same_canonical=same_canonical)
        report.append(row)
        print(json.dumps(row),flush=True)
    (OUT/(case+'-state-drift.json')).write_text(json.dumps(dict(case=case,rows=report),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',default='coupled-wall-run');p.add_argument('--stop',type=int,default=44);a=p.parse_args();main(a.case,a.stop)
