"""Match authored crawl hands with floor-safe collision boxes and a closed cycle."""
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
from idle_contact import fit_idle

def fit_crawl(model, frames, wanted, geometry, tail_frames=8):
    wanted=wanted.copy();names=model.get_body_names()
    # Close source targets with the same cycle displacement as the policy clip.
    travel=frames[-1,:3]-frames[0,:3]
    u=np.linspace(0.,1.,tail_frames);blend=u*u*(3.-2.*u)
    for j in range(len(names)):
        delta=wanted[0,j,:3,3]+travel-wanted[-1,j,:3,3]
        wanted[-tail_frames:,j,:3,3]+=blend[:,None]*delta
        rotations=R.from_matrix(wanted[:,j,:3,:3])
        delta=(rotations[-1].inv()*rotations[0]).as_rotvec()
        wanted[-tail_frames:,j,:3,:3]=(rotations[-tail_frames:]*R.from_rotvec(blend[:,None]*delta)).as_matrix()
    # Fit at physics frequency: fitting only 30-Hz keys can leave a dipping
    # contact trajectory between keys when a hand rotates quickly.
    factor=8;times=np.arange(len(frames));dense=np.linspace(0,len(frames)-1,(len(frames)-1)*factor+1)
    ff=np.stack([np.interp(dense,times,frames[:,i]) for i in range(frames.shape[1])],-1)
    channels=[3]+[6+model.get_joint(j).dof_idx for j in range(1,model.get_num_joints()) if model.get_joint(j).get_dof_dim()==3]
    for start in channels:ff[:,start:start+3]=Slerp(times,R.from_rotvec(frames[:,start:start+3]))(dense).as_rotvec()
    ww=np.tile(np.eye(4),(len(dense),len(names),1,1))
    for j in range(len(names)):
        for axis in range(3):ww[:,j,axis,3]=np.interp(dense,times,wanted[:,j,axis,3])
        ww[:,j,:3,:3]=Slerp(times,R.from_matrix(wanted[:,j,:3,:3]))(dense).as_matrix()
    frames=ff.astype(np.float32);wanted=ww
    clearance=[];source_bottoms=[]
    for name in ('right_hand','left_hand'):
        j=names.index(name);g=next(x for x in geometry['shapes'] if x['bone']==name)
        r=wanted[:,j,:3,:3]
        bottom=wanted[:,j,2,3]+(r@np.array(g['position']))[:,2]-np.abs((r@np.array(g['axes']))[:,2,:])@(np.array(g['dimensions'])/2)
        source_bottoms.append(bottom)
        # Keep authored swing clearance. Only raise boxes that cross the floor;
        # both hands are not forced onto the ground during the whole animation.
        clearance.append(np.maximum(bottom,0.))
    clearance=np.stack(clearance,-1)
    fitted,report=fit_idle(model,frames,wanted,geometry,hand_clearance=clearance)
    return fitted,dict(fitting=report,resample_factor=factor,clearance_m=clearance.tolist(),source_box_bottom_m=np.stack(source_bottoms,-1).tolist(),
        source_hand_xy_preserved_except_loop_seam=True,hand_orientation_preserved_except_loop_seam=True,
        root_and_legs_preserved=True)
