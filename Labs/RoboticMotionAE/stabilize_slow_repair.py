"""Remove independent-IK branch changes from an almost-static sitting clip."""
import pickle,json,sys
import numpy as np
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry,OUT,write,coords
from validate_slow_repair import dense,validate

def project(g,f,margin=.001):
    f=f.copy()
    for mj in g.meta['joints']:
        j=g.k.get_joint(g.names.index(mj['body']));a=6+j.dof_idx;n=j.get_dof_dim()
        if n==1:
            f[a]=np.clip(f[a],mj['range_rad'][0]+margin,mj['range_rad'][1]-margin);continue
        ref=R.from_quat(np.array(mj['reference_wxyz'])[[1,2,3,0]])
        q=(ref*R.from_rotvec(f[a:a+3])).as_quat()[[3,0,1,2]];c=coords(q)
        c[0]=np.clip(c[0],-mj['limits_rad'][0]+margin,mj['limits_rad'][0]-margin)
        axes=np.sin(np.array(mj['limits_rad'][1:])/2);rad=np.linalg.norm(c[1:]/axes)
        if rad>np.sqrt(1-margin):c[1:]*=np.sqrt(1-margin)/rad
        s=np.sqrt(1-c[1:]@c[1:]);ct,st=np.cos(c[0]/2),np.sin(c[0]/2);y,z=c[1:]
        f[a:a+3]=(ref.inv()*R.from_quat([s*st,y*ct+z*st,z*ct-y*st,s*ct])).as_rotvec()
    return f

def sitting(name='sitting'):
    g=Geometry();path=OUT/'candidates'/f'{name}.pkl';data=pickle.loads(path.read_bytes());npz=np.load(path.with_suffix('.npz'))
    before=npz['before'];after=npz['after'];wanted=npz['wanted']
    # Use one coherent correction for the entire nearly static source, rather
    # than allowing a per-frame solver to switch equivalent leg/arm branches.
    scores=[]
    for i,f in enumerate(after):
        p,r=g.fk(f);scores.append(np.square(p-wanted[i,:,:3,3]).sum())
    for scale in (1.,.5,0.):
        for anchor in np.argsort(scores)[::3]:
            corrected=before.astype(float).copy();corrected[:,2]+=after[anchor,2]-before[anchor,2]
            for j in g.joints:
                a=6+j.dof_idx;n=j.get_dof_dim()
                if n==1:corrected[:,a]=after[anchor,a]+scale*(before[:,a]-before[anchor,a])
                else:
                    source=R.from_rotvec(before[:,a:a+3]);base=R.from_rotvec(before[anchor,a:a+3]);target=R.from_rotvec(after[anchor,a:a+3])
                    deviation=(base.inv()*source).as_rotvec()*scale
                    corrected[:,a:a+3]=(target*R.from_rotvec(deviation)).as_rotvec()
            corrected=np.array([project(g,f) for f in corrected])
            minimum=1.
            for f in corrected:
                if g.distances(f).min()<.0005:break
                minimum=min(minimum,g.floors().min())
            else:
                corrected[:,2]+=max(0.,.001-minimum)
                expanded=dense(g,corrected)
                good=True;floor=1.
                for f in expanded:
                    if g.distances(f).min()<.0001 or any(g.limits(f).values()):good=False;break
                    floor=min(floor,g.floors().min())
                if good:
                    corrected[:,2]+=max(0.,.001-floor)
                    data['frames']=corrected.astype(np.float32);path.write_bytes(pickle.dumps(data))
                    np.savez_compressed(path.with_suffix('.npz'),before=before,after=data['frames'],wanted=wanted)
                    write(OUT/(name+'-coherent-correction.json'),dict(anchor_frame=int(anchor),source_joint_motion_scale=scale,method='One constant retarget correction per joint, preserving original motion variation and projecting into the existing limits',after=g.audit(data['frames'])))
                    result=validate(path);assert result['passed'];return
    raise RuntimeError('No coherent sitting correction passed geometry and joint checks')

if __name__=='__main__':sitting(sys.argv[1] if len(sys.argv)>1 else 'sitting')
