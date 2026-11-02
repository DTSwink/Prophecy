"""Add clearance where reference interpolation still violates feasibility."""
import pickle,sys,json
import numpy as np
from repair_slow_targets import Geometry,OUT,repair_frame,write
from stabilize_slow_repair import project
from validate_slow_repair import dense,validate

def refine(name):
    g=Geometry();path=OUT/'candidates'/f'{name}.pkl';data=pickle.loads(path.read_bytes());a=np.load(path.with_suffix('.npz'))
    f=a['after'].astype(float).copy();before=a['before'];wanted=a['wanted']
    # Small interior margin for quaternion interpolation of the PHAT ellipse.
    f=np.array([project(g,x,margin=.02) for x in f])
    reports=[]
    for sweep in range(4):
        expanded=dense(g,f);bad=set();height=np.zeros(len(f))
        for i,x in enumerate(expanded):
            ds=g.distances(x).min();floor=g.floors().min();lim=g.limit_margin(x).min()
            k=min(i//8,len(f)-2)
            if ds<.0005 or lim<-1e-6:bad.update((k,k+1))
            if floor<.001:height[k:k+2]=np.maximum(height[k:k+2],.001-floor)
        f[:,2]+=height
        print(name,'sweep',sweep,'bad',sorted(bad),'max lift',height.max(),flush=True)
        if not bad:break
        for i in sorted(bad):
            new,receipt=repair_frame(g,before[i],wanted[i],f[i],before[i],maxiter=100,clearance=.015+.005*sweep,joint_safety=.02,rotation_weight=2.)
            assert receipt['actual_min_clearance']>0 and receipt['actual_limit_margin']>=-1e-6,(name,i,receipt)
            f[i]=new;reports.append(dict(frame=i,sweep=sweep,**receipt))
    data['frames']=f.astype(np.float32);path.write_bytes(pickle.dumps(data));np.savez_compressed(path.with_suffix('.npz'),before=before,after=data['frames'],wanted=wanted)
    write(OUT/(name+'-refinement.json'),reports)
    report=validate(path);assert report['passed'],report

if __name__=='__main__':refine(sys.argv[1])
