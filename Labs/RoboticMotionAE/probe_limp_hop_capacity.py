"""Local, policy-free push-off search under the deployed actuator/contact limits.

No provider calls. Zero initial velocities; never resets during a trial. A witness
is capacity evidence, not a demonstration of learned or repeatable locomotion.
"""
import os, json, pickle, time, sys
import preflight_slow_policy as p
import numpy as np
import torch
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry

def main():
    out=p.out/'limp-mechanical-capacity-20261101';out.mkdir(exist_ok=True)
    g=Geometry()
    os.chdir(p.p/'MimicKit');torch.set_num_threads(2);torch.set_num_interop_threads(1)
    p.wp.init();p.wp.set_device('cuda:0');p.mp_util.init(0,1,'cuda:0',6763)
    cfg,ec=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine')]
    env=p.SlowLocoEnv(cfg,ec,512,'cuda:0',False);eng=env._engine;char=env._get_char_id();env.reset()
    ids=env._fixed_motion_ids.cpu().numpy();rows=np.flatnonzero((ids==4)|(ids==5));n=len(rows)
    rt=torch.tensor(rows,device='cuda:0');mask=p.wp.to_torch(eng.transfer_contact.p.motor_enabled)
    mass=eng._sim_model.body_mass.numpy().reshape(512,15)[0].copy()
    offsets=eng._sim_model.body_com.numpy().reshape(512,15,3)[0].copy()
    frames=[];supports=[];disabled=[];source_frames=[]
    for row in rows:
        clip=pickle.loads((p.p/'motions'/(env.motion_labels[ids[row]]+'.pkl')).read_bytes())
        k=int(np.argmin(clip['frames'][:,2]));f=clip['frames'][k].copy()
        # Same deepest authored crouch for every candidate of a given side.
        f[:2]=0
        frames.append(f);source_frames.append(k)
        supports.append(env.disabled_dof_indices['right' if ids[row]==4 else 'left'])
        disabled.append(env.disabled_dof_indices['left' if ids[row]==4 else 'right'])
    frames=np.array(frames);supports=np.array(supports);disabled=np.array(disabled)
    rng=np.random.default_rng(20261103);best={};records=[]
    initial_q=torch.tensor(frames[:,6:],device='cuda:0',dtype=torch.float32)
    def init():
        env.reset()
        eng.set_root_pos(rt,char,torch.tensor(frames[:,:3],device='cuda:0',dtype=torch.float32))
        eng.set_root_rot(rt,char,torch.tensor(R.from_rotvec(frames[:,3:6]).as_quat(),device='cuda:0',dtype=torch.float32))
        eng.set_dof_pos(rt,char,initial_q)
        eng.set_root_vel(rt,char,0.);eng.set_root_ang_vel(rt,char,0.);eng.set_dof_vel(rt,char,0.)
        eng._sim_state.pre_step_update();eng._sim_state.eval_fk()
    def measure():
        pos=eng.get_body_pos(char)[rt].cpu().numpy();quat=eng.get_body_rot(char)[rt].cpu().numpy()
        rot=R.from_quat(quat.reshape(-1,4)).as_matrix().reshape(n,15,3,3)
        bc=pos+np.einsum('nbij,bj->nbi',rot,offsets)
        com=np.einsum('nbi,b->ni',bc,mass)/mass.sum()
        gp=pos[:,g.gb]+np.einsum('ngij,gj->ngi',rot[:,g.gb],g.gp)
        gr=rot[:,g.gb]@g.gr
        bottom=np.empty((n,len(g.gs)))
        for j,geom in enumerate(g.gs):
            s=geom['size'];extent=np.abs(gr[:,j,2])@s if geom['type']=='box' else s[0]+abs(gr[:,j,2,2])*s[1]
            bottom[:,j]=gp[:,j,2]-extent
        feet=np.stack([bottom[:,g.gb==g.names.index(side+'_foot')].min(1) for side in ('right','left')],1)
        return com,feet,bottom.min(1),pos,quat
    for trial in range(8):
        init();q0=eng.get_dof_pos(char).clone()
        # Position-servo targets converted to bounded velocity commands. Search
        # hip flexion, extension timing and ankle push without learned actions.
        params=np.column_stack([rng.uniform(-.5,.3,n),rng.uniform(0,.22,n),rng.uniform(-.8,.6,(n,3)),rng.uniform(10,45,n),rng.integers(4,13,n)])
        if trial>0:
            for motion in (4,5):
                rr=np.flatnonzero(ids[rows]==motion)
                if motion in best:
                    parent=np.array(best[motion]['params']);params[rr[:len(rr)//2]]=parent+rng.normal(size=(len(rr)//2,7))*np.array([.12,.08,.15,.15,.15,5,1])
        params[:,1]=np.clip(params[:,1],0,.25);params[:,5]=np.clip(params[:,5],8,50);params[:,6]=np.clip(np.round(params[:,6]),3,14)
        target=q0.clone();vals=initial_q.cpu().numpy()[np.arange(n)[:,None],supports].copy()
        vals[:,2]=params[:,0];vals[:,3]=params[:,1];vals[:,4:7]=params[:,2:5]
        target[rt[:,None],torch.tensor(supports,device='cuda:0')]=torch.tensor(vals,device='cuda:0',dtype=torch.float32)
        gains=torch.ones((512,1),device='cuda:0')*12;gains[rt]=torch.tensor(params[:,5:6],device='cuda:0',dtype=torch.float32)
        history=[];forces=[];commands=[]
        history.append(measure());zero_peak=0.
        for tick in range(36):
            q=eng.get_dof_pos(char);action=(target-q)*gains
            # After extension, hold the reached target; no external impulse.
            before=torch.tensor(tick>=params[:,6],device='cuda:0')
            action[rt[before]]=(q0[rt[before]]-q[rt[before]])*10
            action=torch.minimum(torch.maximum(action,env._action_bound_low),env._action_bound_high)
            eng.set_cmd(char,action);eng.step()
            history.append(measure());forces.append(eng._dof_forces[0][rt].cpu().numpy().copy());commands.append(action[rt].cpu().numpy().copy())
            zero_peak=max(zero_peak,float(np.abs(forces[-1][np.arange(n)[:,None],disabled]).max()))
        com=np.array([x[0] for x in history]);feet=np.array([x[1] for x in history]);floor=np.array([x[2] for x in history]);vel=np.gradient(com,1/30,axis=0)
        airborne=(feet.min(2)>.01)&(floor>.005)
        # Reject incidental clearance while falling: positive COM rise and an
        # ascending airborne interval are required. Require 3 consecutive ticks.
        valid=airborne&(com[:,:,2]>com[0,:,2]+.02)
        triple=valid[:-2]&valid[1:-1]&valid[2:]
        success=triple.any(0)&(airborne&(vel[:,:,2]>.1)).any(0)
        score=np.where(success,10.,0.)+np.max(np.where(airborne,vel[:,:,2],-10),axis=0)+np.maximum(vel[:16,:,2].max(0),0)*.1
        for motion in (4,5):
            rr=np.flatnonzero(ids[rows]==motion);i=rr[np.argmax(score[rr])]
            rec=dict(trial=trial,motion=env.motion_labels[motion],row=int(rows[i]),source_frame=int(source_frames[i]),params=params[i].tolist(),success=bool(success[i]),score=float(score[i]),peak_up_speed=float(vel[:,i,2].max()),com_rise_m=float(com[:,i,2].max()-com[0,i,2]),airborne_ticks=np.flatnonzero(airborne[:,i]).tolist(),max_both_foot_clearance_m=float(feet[:,i].min(1).max()),max_disabled_torque_nm=zero_peak,peak_support_torque_nm=np.abs(np.array(forces)[:,i][:,supports[i]]).max(0).tolist())
            records.append(rec)
            if motion not in best or rec['score']>best[motion]['score']:
                best[motion]=rec
                np.savez_compressed(out/(env.motion_labels[motion]+'-best.npz'),com=com[:,i],feet=feet[:,i],floor=floor[:,i],pos=np.array([h[3][i] for h in history]),quat=np.array([h[4][i] for h in history]),forces=np.array(forces)[:,i],commands=np.array(commands)[:,i],initial_frame=frames[i],params=params[i],support=supports[i],disabled=disabled[i])
        report=dict(method='policy-free bounded velocity servo shooting; zero initial velocity; authored deepest crouch; actual deployed simulator',mass_kg=float(mass.sum()),hip_nm=200,knee_nm=300,ankle_nm=180,all_trials=records,best=best)
        (out/'report.json').write_text(json.dumps(report,indent=2));print('CAPACITY '+json.dumps({'trial':trial,'best':best}),flush=True)

if __name__=='__main__':main()
