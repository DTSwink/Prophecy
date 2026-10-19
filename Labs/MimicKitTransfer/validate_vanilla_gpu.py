"""Disposable native MJWarp verification. Imports no custom physics code.

Inference/state readback is on CPU for diagnosis only. GPU timings separately
measure captured physics for512worlds, NOT end-to-end PPO throughput.
"""
import argparse,json,time
from pathlib import Path
import numpy as np
import mujoco,mujoco_warp as mjw,warp as wp,torch
from scipy.spatial.transform import Rotation as R


def decode(m,d,names,q,v):
    d.qpos[:]=q;d.qvel[:]=v
    mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d)
    rows=[]
    for name in names:
        b=next(b for b in range(1,m.nbody) if m.body(b).name.endswith(name))
        jp=np.zeros((3,m.nv));jr=jp.copy();mujoco.mj_jacBodyCom(m,d,jp,jr,b)
        rows.append(np.r_[d.xpos[b],np.roll(d.xquat[b],-1),jp@v,jr@v])
    return np.asarray(rows)


def observation(state,commands,meta):
    rot=R.from_quat(state[:,3:7]);joint=[];vel=[]
    for i in range(1,15):
        local=R.from_quat(meta['rest_xyzw'][i])
        rel=local.inv()*rot[meta['parents'][i]].inv()*rot[i]
        mat=rel.as_matrix();joint.extend(np.r_[mat[:,0],mat[:,2]])
        angular=rot[i].inv().apply(state[i,10:13]-state[meta['parents'][i],10:13])
        vel.extend(angular if meta['ball'][i] else [angular[2]])
    mat=rot[0].as_matrix()
    return np.r_[state[0,2],mat[:,0],mat[:,2],state[0,7:13],joint,vel,
                 (state[meta['keys'],:3]-state[0,:3]).reshape(-1),commands].astype(np.float32)


def actor(obs,ck):
    x=torch.as_tensor(obs,dtype=torch.float32)
    x=((x-ck['_obs_norm._mean'])/ck['_obs_norm._std']).clamp(-10,10)
    with torch.no_grad():
        for i in (0,2,4):
            key='_model._actor_layers.'+str(i)
            x=torch.relu(torch.nn.functional.linear(x,ck[key+'.weight'],ck[key+'.bias']))
        x=torch.nn.functional.linear(x,ck['_model._action_dist._mean_net.weight'],ck['_model._action_dist._mean_net.bias'])
        return (x*ck['_a_norm._std']+ck['_a_norm._mean']).numpy()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);a=ap.parse_args();folder=a.folder
    meta=json.loads((folder/'packet.json').read_text());z=dict(np.load(folder/'packet.npz'))
    ck=torch.load(folder/'actor.pt',map_location='cpu',weights_only=True);torch.set_num_threads(1)
    wp.init();wp.set_device('cuda:0');results={'versions':dict(mujoco=mujoco.__version__,mjwarp=mjw.__version__,warp=wp.__version__),'device':wp.get_device().name,'evaluations':{}}
    for name in meta['candidates']:
        m=mujoco.MjModel.from_binary_path(str(folder/(name+'.mjb')));d=mujoco.MjData(m)
        assert abs(m.opt.timestep-1/240)<1e-12
        wm=mjw.put_model(m);wd=mjw.make_data(m,nworld=16,nconmax=150,njmax=450)
        motors=np.flatnonzero(m.actuator_biasprm[:,2]!=0)
        q=z[name+'_q'];v=z[name+'_v'];wd.qpos.assign(q);wd.qvel.assign(v)
        with wp.ScopedCapture() as cap:
            for _ in range(8):mjw.step(wm,wd)
        wd.qpos.assign(q);wd.qvel.assign(v);wd.qacc_warmstart.zero_()
        current=z['initial'].copy();history=[current.copy()];first_failure=np.full(16,300);peak=np.zeros(16);alive=np.ones(16,bool)
        for t in range(300):
            obs=np.array([observation(s,z['commands'][t,w],meta) for w,s in enumerate(current)])
            if t==0:
                err=float(abs(obs-z['initial_obs']).max());assert err<1e-3,err
                err=float(abs(actor(obs,ck)-z['initial_actions']).max());assert err<2e-3,err
            ctrl=np.zeros((16,m.nu),np.float32);ctrl[:,motors]=actor(obs,ck).clip(-2*np.pi,2*np.pi)
            wd.ctrl.assign(ctrl);wp.capture_launch(cap.graph)
            q=wd.qpos.numpy();v=wd.qvel.numpy()
            if not np.isfinite(q).all() or not np.isfinite(v).all():raise RuntimeError('Nonfinite native state')
            current=np.array([decode(m,d,meta['names'],qq,vv) for qq,vv in zip(q,v)])
            history.append(current.copy())
            for w in range(16):
                target=z['targets'][t,w].copy();target[:,:2]+=current[w,0,:2]-target[0,:2]
                ids=meta['keys'];offset=np.asarray(meta['offsets'])
                actual=current[w,ids,:3]+R.from_quat(current[w,ids,3:7]).apply(offset)
                expected=target[ids,:3]+R.from_quat(target[ids,3:7]).apply(offset)
                dist=float(np.linalg.norm(actual-expected,axis=1).max())
                if alive[w]:peak[w]=max(peak[w],dist)
                if alive[w] and dist>.27:first_failure[w]=t+1;alive[w]=False
            if not alive.any():break
        results['evaluations'][name]=dict(passes=int(alive.sum()),ticks=first_failure.tolist(),peak_target_m=peak.tolist())
        np.savez_compressed(folder/(name+'_gpu.npz'),states=np.asarray(history,np.float32))
        print(json.dumps({name:results['evaluations'][name]}),flush=True)
        (folder/'gpu-results.json').write_text(json.dumps(results,indent=2))
        del wd,wm,cap
    # Paired captured physics; identical16starts tiled32times, constant first commands.
    graphs={};keep=[]
    for name in meta['candidates']:
        m=mujoco.MjModel.from_binary_path(str(folder/(name+'.mjb')))
        wm=mjw.put_model(m);wd=mjw.make_data(m,nworld=512,nconmax=150,njmax=450)
        q=wp.array(np.tile(z[name+'_q'],(32,1)).astype(np.float32));v=wp.array(np.tile(z[name+'_v'],(32,1)).astype(np.float32))
        ctrl=np.zeros((512,m.nu),np.float32);motors=np.flatnonzero(m.actuator_biasprm[:,2]!=0)
        ctrl[:,motors]=np.tile(z['initial_actions'].clip(-2*np.pi,2*np.pi),(32,1));wd.ctrl.assign(ctrl)
        with wp.ScopedCapture() as cap:
            wp.copy(wd.qpos,q);wp.copy(wd.qvel,v);wd.qacc_warmstart.zero_()
            for _ in range(8):mjw.step(wm,wd)
        graphs[name]=cap.graph;keep.append((wm,wd,q,v,cap))
    samples={name:[] for name in graphs};begin=wp.Event(enable_timing=True);end=wp.Event(enable_timing=True)
    for repeat in range(24):
        order=list(graphs) if repeat%2 else list(reversed(graphs))
        for name in order:
            wp.record_event(begin);wp.capture_launch(graphs[name]);wp.record_event(end)
            ms=wp.get_event_elapsed_time(begin,end)
            if repeat>=4:samples[name].append(ms)
    results['physics_512_ms']={name:float(np.median(values)) for name,values in samples.items()}
    results['physics_samples_ms']=samples
    results['timing_scope']='Captured8nativephysicsstepsplusGPUreset,512worlds,240Hz; noPPO/inference/transfer time. Different trajectories, same initial states and commands.'
    (folder/'gpu-results.json').write_text(json.dumps(results,indent=2));print(json.dumps(results),flush=True)

if __name__=='__main__':main()
