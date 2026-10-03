"""Isolated temporary upper-only root-rotation horizon experiment (localhost only)."""
from pathlib import Path
import json, sys, threading, time, copy, os, multiprocessing, queue
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ProcessPoolExecutor
import subprocess

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
STEPPER = Path('C:/Users/singerie/Documents/Cursor/stepper')
DATA = PROJECT / 'Saved/Diagnostics/TurnParity'
BASE_PAYLOAD = json.loads((STEPPER/'training/rollout_debug_viewer/turn_parity_temp.json').read_text())
LOCK = threading.Lock()
CACHE = {}
STATE = None
WORKER = None
PROGRESS_QUEUE = None
JOBS = {}
JOB_LOCK = threading.Lock()
PROGRESS = 'Idle'

def progress(message):
    global PROGRESS
    PROGRESS=message
    if PROGRESS_QUEUE is not None:PROGRESS_QUEUE.put(message)

def initialize_worker(progress_queue):
    global PROGRESS_QUEUE
    PROGRESS_QUEUE=progress_queue

def current_progress():
    global PROGRESS
    with JOB_LOCK:
        try:
            while True:PROGRESS=PROGRESS_QUEUE.get_nowait()
        except queue.Empty:pass
    return PROGRESS

def benchmark_running():
    # This isolated helper runs below normal priority with one inference thread.
    # Never block its HTTP responder on machine-wide process enumeration.
    return False

def yield_to_benchmark():
    while benchmark_running():
        progress('Waiting for the main benchmark to finish')
        time.sleep(2)

def initialize():
    global STATE
    if STATE is not None:
        return STATE
    yield_to_benchmark()
    progress('Loading the upper NN and recorded lower rollout')
    import numpy as np
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    sys.path.insert(0, str(STEPPER))
    from training.ik import train_upper_pose_controller_pelvis as ctl
    from training.ik import train_upper_pose_controller as rt
    from training.ik import train_upper_pose_autoencoder as ud
    from training.ik import ik_core as tl, visualize
    contract = json.loads((PROJECT/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
    cp = torch.load(contract['checkpoint_path'], map_location='cpu', weights_only=False)
    lowerpath = Path(cp['metadata']['lower_selection']['walk']['checkpoint'])
    if not lowerpath.is_absolute(): lowerpath = STEPPER/lowerpath
    lowercp = torch.load(lowerpath, map_location='cpu', weights_only=False)
    device = torch.device('cpu')
    cfg = rt.apply_checkpoint_config(lowercp, device)
    relative = 'walk_transitions/M_Neutral_Stand_Turn_180_R.npz'
    clip = tl.MotionClip(ud.ORIGINAL_ROOT/relative, cfg, cyclic_animation=False)
    lower_model = visualize.load_model(lowercp, clip, cfg, device)
    lower_model.eval()
    runtime = rt.build_category_runtime('walk', [relative], lowercp, cfg, lower_model, device)
    runtime.install_policy()
    model = ctl.UpperCachedLowerAgent()
    model.load_state_dict(cp['model']); model.eval()
    rows = [json.loads(line) for line in (DATA/'current_inputs.jsonl').read_text().splitlines()]
    rows = [r for r in rows if r['actor'] == 'BP_ProphecyManualPoseAgent_C_1']
    recorded = np.load(DATA/'coupled_4.npz')
    n = len(recorded['times'])
    ux = torch.tensor(np.load(DATA/'ue_upper_replay.npz')['inputs'][:n])
    roots = torch.tensor([r['roots'] for r in rows[:n]])
    seed = torch.tensor([[1.,0,0],[0,0,-1],[0,1,0]])
    lower = torch.tensor(recorded['lower']).clone()
    # Decode each unchanged lower prediction in the actual next-root frame.
    a = roots[:,7] - roots[:,11]
    bridge = torch.eye(3).repeat(n,1,1)
    bridge[:,0,0]=a.cos(); bridge[:,0,2]=a.sin(); bridge[:,2,0]=-a.sin(); bridge[:,2,2]=a.cos()
    bridge = seed@bridge@seed.T
    for off in [0,9,25]: lower[:,off:off+3] = (lower[:,off:off+3].unsqueeze(1)@bridge).squeeze(1)
    for off in [3,12,18,28,34]: lower[:,off:off+6] = tl.rotmat_to_6d(tl.rotation_6d_to_matrix(lower[:,off:off+6])@bridge)
    a = roots[:,7]
    heading = torch.eye(3).repeat(n,1,1)
    heading[:,0,0]=a.cos(); heading[:,0,2]=-a.sin(); heading[:,2,0]=a.sin(); heading[:,2,2]=a.cos()
    rootrot = seed@heading
    rootpos = roots[:,4:7].clone()
    rootpos[:,0] -= rootpos[0,0].item(); rootpos[:,2] -= rootpos[0,2].item()
    initial_lower = torch.tensor([rows[0]['lower_input'][:41]])
    current_lower = torch.cat([initial_lower, lower[:-1]],0)
    def transform(state, p, r):
        return torch.cat([state[:,p:p+3]@seed,
            tl.rotmat_to_6d(tl.rotation_6d_to_matrix(state[:,r:r+6])@seed)],-1)
    pelvis = transform(lower,0,3)
    rest = runtime.rest_offsets_by_mode[1.][0]
    full = runtime.full_by_mode[1.]
    def make_base(pel):
        rot = tl.rotation_6d_to_matrix(pel[:,3:])
        parts = [torch.tensor([1.,0,0,0,1,0]).repeat(len(pel),10)]
        for name in ['hand_l','hand_r']:
            hp=(rest[full.body_names.index(name)][None,None,:]@rot).squeeze(1)+pel[:,:3]
            parts.extend([hp,pel[:,3:],pel[:,3:]])
        return ud.clean_upper_state(torch.cat(parts,-1))
    pprev = torch.cat([ux[:1,180:189],ux[:1,189:198],pelvis[:-2]],0)
    pcur = torch.cat([ux[:1,189:198],pelvis[:-1]],0)
    conditions = torch.cat([pprev,pcur,pelvis,ux[:,207:243],
        transform(current_lower,9,12),transform(current_lower,25,28),
        transform(lower,9,12),transform(lower,25,28),ux[:,279:]],-1)
    with torch.inference_mode():
        bases = make_base(pelvis)
        initial_base = make_base(ux[:1,189:198])
    STATE = dict(np=np, torch=torch, ctl=ctl, rt=rt, ud=ud, runtime=runtime, model=model,
        conditions=conditions, bases=bases, initial_base=initial_base,
        initial_prev=ux[:1,:90].clone(), initial_current=torch.tensor([rows[0]['previous_upper']]),
        lower=lower, pelvis=pelvis, rootpos=rootpos, rootrot=rootrot, heading=heading,
        expected_upper=recorded['upper'], times=recorded['times'], n=n,
        roots=roots, speed_scale=float(cfg.max_speed_scale_final))
    return STATE

def replay(factor):
    s=initialize(); np=s['np']; torch=s['torch']; ud=s['ud']
    condition=s['conditions'].clone()
    # Within conditioning, root features start after the three nine-value pelvis records.
    # First three root features (current velocities) and all future positions stay exact.
    blocks=condition[:,30:62].reshape(s['n'],8,4)
    original_angles=np.arctan2(blocks[:,:,3].numpy(),blocks[:,:,2].numpy())
    anchored=np.unwrap(np.concatenate([np.zeros((s['n'],1)),original_angles],axis=1),axis=1)
    samples=np.arange(1,9,dtype=float)*factor
    angles=np.stack([np.interp(samples,np.arange(9),a) for a in anchored])
    if factor != 1.0:
        blocks[:,:,2]=torch.tensor(np.cos(angles),dtype=blocks.dtype)
        blocks[:,:,3]=torch.tensor(np.sin(angles),dtype=blocks.dtype)
    # Assert the intervention changes only the 16 future cosine/sine values.
    allowed=np.zeros(condition.shape[1],dtype=bool)
    for k in range(8): allowed[32+4*k:34+4*k]=True
    assert torch.equal(condition[:,~allowed],s['conditions'][:,~allowed])
    previous=s['initial_prev'].clone(); current=s['initial_current'].clone(); base=s['initial_base']
    result=[]
    with torch.inference_mode():
        for i in range(s['n']):
            if i % 30 == 0:
                yield_to_benchmark()
                progress(f'Replaying upper NN: {i} / {s["n"]} frames')
            newbase=s['bases'][i:i+1]
            prior=ud.clean_upper_state(newbase+current-base)
            features=torch.cat([previous,prior,condition[i:i+1]],-1)
            following=ud.clean_upper_state(prior+s['model'](features))
            result.append(following[0]); previous,current=current,following; base=newbase
        upper=torch.stack(result)
        p,q=s['ctl'].decode_rows(s['runtime'],1.,s['lower'],upper,s['pelvis'],s['rootpos'],
            s['rootrot'],s['heading'],torch.zeros(s['n'],dtype=torch.long))
    return upper.numpy(),p.numpy(),q.numpy(),angles

def attach_window(data,angles):
    s=STATE;np=s['np']
    original=s['conditions'][:,30:62].numpy().reshape(s['n'],8,4)
    roots=s['roots'].numpy()
    anchor=roots[:,8:11].copy()
    anchor[:,0]-=float(roots[0,4]);anchor[:,2]-=float(roots[0,6]);anchor[:,1]=0.012
    yaw=roots[:,11]
    local=original[:,:,:2]*(np.arange(1,9)[None,:,None]*s['speed_scale'])
    positions=np.repeat(anchor[:,None,:],9,axis=1)
    positions[:,1:,0]+=local[:,:,0]*np.cos(yaw[:,None])+local[:,:,1]*np.sin(yaw[:,None])
    positions[:,1:,2]+=-local[:,:,0]*np.sin(yaw[:,None])+local[:,:,1]*np.cos(yaw[:,None])
    world_yaw=np.concatenate([yaw[:,None],yaw[:,None]+angles],axis=1)
    directions=np.stack([np.sin(world_yaw),np.zeros_like(world_yaw),np.cos(world_yaw)],axis=-1)
    selections=[np.flatnonzero((s['times']>=7.55)&(s['times']<9.95)),np.arange(s['n'])]
    data['upper_root_window_positions']=[positions[sel].tolist() for sel in selections]
    data['upper_root_window_forwards']=[directions[sel].tolist() for sel in selections]
    data['metadata']['root_window_source']='Exact resampled future orientation features supplied to upper NN; root0 is its input anchor; projected onto floor.'

def generate(factor):
    with LOCK:
        if factor in CACHE: return CACHE[factor]
        if 'validated' not in CACHE:
            upper,p,q,_=replay(1.0)
            np=STATE['np']
            error=float(np.max(abs(upper-STATE['expected_upper'])))
            selections=[np.flatnonzero((STATE['times']>=7.55)&(STATE['times']<9.95)),np.arange(STATE['n'])]
            pose_error=max(float(np.max(abs(p[selection]-np.array(BASE_PAYLOAD['positions'][i])))) for i,selection in enumerate(selections))
            rotation_error=max(float(np.max(abs(q[selection]-np.array(BASE_PAYLOAD['basis'][i])))) for i,selection in enumerate(selections))
            report=dict(baseline_upper_max_abs=error,baseline_position_max_m=pose_error,baseline_rotation_matrix_max_abs=rotation_error)
            (HERE/'validation.json').write_text(json.dumps(report,indent=2))
            assert error<0.0001 and pose_error<0.0001 and rotation_error<0.0001, report
            CACHE['validated']=True
            baseline=copy.deepcopy(BASE_PAYLOAD)
            baseline['metadata']['upper_rotation_horizon']=1.0
            baseline['metadata']['lower_rollout_unchanged']=True
            attach_window(baseline,replay_angles(1.0))
            CACHE[1.0]=baseline
        if factor in CACHE: return CACHE[factor]
        upper,p,q,angles=replay(factor)
        np=STATE['np']; full=STATE['runtime'].full_by_mode[1.]
        # Lower-body transforms must remain identical, not merely similar.
        lower_names=['pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r']
        ids=[list(full.body_names).index(name) for name in lower_names]
        data=copy.deepcopy(BASE_PAYLOAD)
        selections=[np.flatnonzero((STATE['times']>=7.55)&(STATE['times']<9.95)),np.arange(STATE['n'])]
        for i,sel in enumerate(selections):
            reference_p=np.array(BASE_PAYLOAD['positions'][i]); reference_q=np.array(BASE_PAYLOAD['basis'][i])
            assert np.max(abs(p[sel][:,ids]-reference_p[:,ids]))<0.00001
            assert np.max(abs(q[sel][:,ids]-reference_q[:,ids]))<0.00001
            data['positions'][i]=p[sel].tolist(); data['basis'][i]=q[sel].tolist()
        data['metadata']['upper_rotation_horizon']=factor
        data['metadata']['lower_rollout_unchanged']=True
        attach_window(data,angles)
        data['message']=f'Upper rotation horizon {factor:.2f}. Actual upper NN replay; lower body unchanged.'
        CACHE[factor]=data
        return data

def replay_angles(factor):
    np=STATE['np'];blocks=STATE['conditions'][:,30:62].numpy().reshape(STATE['n'],8,4)
    a=np.unwrap(np.concatenate([np.zeros((STATE['n'],1)),np.arctan2(blocks[:,:,3],blocks[:,:,2])],axis=1),axis=1)
    return np.stack([np.interp(np.arange(1,9)*factor,np.arange(9),row) for row in a])

def request_replay(factor):
    with JOB_LOCK:
        if factor in CACHE:return CACHE[factor],200
        job=JOBS.get(factor)
        if job is None:
            if benchmark_running():return {'waiting':True,'message':'Waiting for the main benchmark to finish.'},202
            # Discard queued obsolete values; an already running replay finishes safely.
            for key,old in list(JOBS.items()):
                if not old.running() and not old.done():old.cancel();del JOBS[key]
            job=JOBS[factor]=WORKER.submit(generate,factor)
        if job.done():
            try:return job.result(),200
            except Exception as error:return {'error':str(error)},500
        return {'waiting':True,'message':PROGRESS if job.running() else 'Queued behind the current replay'},202

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query=urlparse(self.path)
        if query.path=='/health': data={'ready':True,'benchmark_running':benchmark_running(),'progress':current_progress()};status=200
        elif query.path=='/rollout':
            try:
                factor=float(parse_qs(query.query).get('factor',['1'])[0])
                if not 0<=factor<=1: raise ValueError('Factor must be between 0 and 1')
                factor=round(factor,2)
                current_progress()
                data,status=request_replay(factor)
            except Exception as error:
                import traceback;traceback.print_exc()
                data={'error':str(error)};status=500
        else: data={'error':'Not found'};status=404
        raw=json.dumps(data,separators=(',',':')).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','http://127.0.0.1:8021')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(raw)));self.end_headers()
        try:self.wfile.write(raw)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
    def log_message(self,*args): pass

if __name__=='__main__':
    PROGRESS_QUEUE=multiprocessing.Queue()
    WORKER=ProcessPoolExecutor(max_workers=1,initializer=initialize_worker,initargs=(PROGRESS_QUEUE,))
    print('Upper-only root horizon preview: http://127.0.0.1:8033',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8033),Handler).serve_forever()
