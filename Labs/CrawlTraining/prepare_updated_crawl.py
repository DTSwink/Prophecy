"""Prepare the edited native crawl with contact and upper-body constraints."""
import json,pickle,sys,time,argparse,copy
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
import repair_references as rr
from constrained_contact import ContactIK
from fit_motion_limits import inflate
from test_model import coords
from current_phat import verify_current_phat,sha
from verify_constrained_contact import densify
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/MimicKitCrawl/updated-training-20261017'

class MarginContactIK(ContactIK):
    def __init__(self,model,meta):
        super().__init__(model,meta)
        # Let the head follow the smallest admissible correction instead of
        # forcing its old world orientation through the changed torso.
        self.selected.append('head')
        self.indices=np.concatenate([np.arange(self.slices[n].start,self.slices[n].stop) for n in self.selected])
    def margins(self,f,names,margin_deg=.05):
        result=[]
        for name in names:
            j=self.joints[name];d=f[self.slices[name]]
            delta=R.from_rotvec(d if len(d)==3 else [0,0,d[0]])
            q=(self.ref[name]*delta).as_quat()[[3,0,1,2]]
            v=coords(q);radius=np.linalg.norm(v[1:]);angle=np.arcsin(np.clip(radius,0,1))*1.05
            v[0]*=1.05
            if radius>1e-12:v[1:]*=np.sin(min(angle,np.pi/2))/radius
            result.extend([np.pi/2-angle,np.pi-abs(v[0])])
            lim=np.array(j['limits_rad'])-np.deg2rad(margin_deg)
            if j['kind']=='hinge':
                angle=2*np.arcsin(np.clip(v[2],-1,1));result.extend([lim[2]-angle,lim[2]+angle])
            else:result.extend([lim[0]-v[0],lim[0]+v[0],1-np.sum((v[1:]/np.sin(lim[1:]/2))**2)])
        return np.array(result)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--probe',action='store_true');args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    meta=verify_current_phat(ROOT/'Saved/MimicKitCrawl/package/assets/uefn')
    model=rr.ae.rt.MJCFCharModel('cpu');model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    run=Path(json.loads((ROOT/'Saved/RoboticCrawlAE/pending-run.json').read_text())['run'])
    raw=pickle.loads((run/'data/03_crawl_robotic.pkl').read_bytes())
    rig=json.loads((ROOT/'Saved/MimicKitUEFN/source-rig.json').read_text())
    geo=json.loads((ROOT/'Saved/MimicKitCrawl/geometry.json').read_text())
    original,closure=rr.close_crawl_cycle(model,raw['frames'])
    if not (OUT/'contact-target.pkl').exists():
        source=ROOT/'Saved/MimicKitCrawl/upperbody-limits-20261017/crawl.bvh'
        wanted=rr.wanted_poses(source,model,meta,rig)
        base,report=rr.fit_crawl(model,original,wanted,geo)
        (OUT/'contact-target.pkl').write_bytes(pickle.dumps(dict(frames=base,fps=240.,loop_mode=1)))
        (OUT/'contact-target.json').write_text(json.dumps(report,indent=2))
    base=pickle.loads((OUT/'contact-target.pkl').read_bytes())['frames'].astype(float)
    original=densify(model,original,8)
    ik=MarginContactIK(model,meta)
    indices=sorted(set([0,80,102,280,360]+list(range(0,len(base),32)))) if args.probe else range(len(base)-1)
    results=[];output=[];initial=None;delta=None
    for i in indices:
        start=time.time()
        f,r=ik.solve(base[i],original[i],initial=initial,previous_delta=delta,
                     torso_limits=True,smooth_weight=20.,maxiter=60)
        if r['position_error_m']>=1e-6 or r['minimum_margin']<=-1e-7:
            f,r=ik.solve(base[i],original[i],initial=initial,previous_delta=delta,
                         torso_limits=True,smooth_weight=20.,maxiter=160,hand_xy_tolerance=.002)
            r['hand_xy_tolerance_m']=.002
        r.update(frame=i,seconds=time.time()-start);results.append(r)
        print(json.dumps(r),flush=True) if args.probe or i%24==0 else None
        if not args.probe:
            assert r['position_error_m']<.002001 and r['height_error_m']<1e-6 and r['minimum_margin']>-1e-7,r
            output.append(f);initial=f;delta=f[ik.indices]-original[i,ik.indices]
    if args.probe:(OUT/'probe.json').write_text(json.dumps(results,indent=2));return
    end=output[0].copy();end[:6]=base[-1,:6]
    for n in ik.names:
        if any(v in n for v in ('thigh','shin','foot')):end[ik.slices[n]]=base[-1,ik.slices[n]]
    output.append(end)
    (OUT/'crawl.pkl').write_bytes(pickle.dumps(dict(frames=np.array(output,dtype=np.float32),fps=240.,loop_mode=1)))
    (OUT/'solve.json').write_text(json.dumps(results,indent=2))
    print('Saved new crawl candidate',flush=True)

if __name__=='__main__':main()
