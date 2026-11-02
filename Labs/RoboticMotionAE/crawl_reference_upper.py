"""Keep authored hand rotations and head height while solving arm contact IK."""
from crawl_upper_cycle import *
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import least_squares
from scipy.interpolate import BPoly
import hashlib, sys


def main():
    g=Geometry(); path=OUT/'candidates/crawl.pkl'
    backup=OUT/'before-reference-upper'; backup.mkdir(exist_ok=True)
    if not (backup/'crawl.pkl').exists():
        shutil.copy2(path,backup/'crawl.pkl'); shutil.copy2(path.with_suffix('.json'),backup/'crawl.json')
    m=pickle.loads((backup/'crawl.pkl').read_bytes()); old=m['frames']
    ref=interpolate(g,pickle.loads((OUT/'before/crawl.pkl').read_bytes())['frames'],4)
    rp,rr=fk(g,ref); op,orr=fk(g,old); n=len(old); dt=1/m['fps']; phase=np.linspace(0,54,n)
    prelean=pickle.loads((OUT/'before-pelvis-arm-repair/crawl.pkl').read_bytes())['frames']
    pp,pr=fk(g,prelean); local_axis=unit(g.lp[9]-g.lp[12]); pivot=(g.lp[9]+g.lp[12])/2
    lean=np.deg2rad(14.877558421225395); root=pr[:,0]@R.from_rotvec(local_axis*lean).as_matrix()
    base=old.copy();base[:,3:6]=R.from_matrix(root).as_rotvec()
    base[:,:3]=prelean[:,:3]+np.einsum('nij,j->ni',pr[:,0]-root,pivot)
    base[:,6:9]=prelean[:,6:9]
    for b in [9,12]:
        j=g.k.get_joint(b);base[:,6+j.dof_idx:9+j.dof_idx]=R.from_matrix(g.lr[b].T@root.transpose(0,2,1)@orr[:,b]).as_rotvec()
    initial_p,initial_r=fk(g,base)
    axis=unit(np.einsum('nij,j->ni',root,local_axis))
    # Stabilize the VISIBLE head collider centre, not only the neck attachment.
    # Its authored world rotation remains exact. A single solved height is shared
    # by the whole cycle; contact feasibility cannot introduce vertical bobbing.
    vector=np.einsum('nij,j->ni',initial_r[:,1],g.lp[2]); parallel=axis*np.sum(axis*vector,axis=1)[:,None]
    head_a=(vector-parallel)[:,2]; head_b=np.cross(axis,vector)[:,2]; head_c=parallel[:,2]
    head_gi=next(i for i,s in enumerate(g.gs) if s['body']=='head')
    head_offset_z=np.einsum('nij,j->ni',rr[:,2],g.gp[head_gi])[:,2]
    reference_head_centre=rp[:,2,2]+head_offset_z
    old_head_centre=op[:,2,2]+np.einsum('nij,j->ni',orr[:,2],g.gp[head_gi])[:,2]
    print('head centre before/reference range cm',np.ptp(old_head_centre)*100,np.ptp(reference_head_centre)*100,flush=True)
    guide=ref.copy()
    for sl in [slice(3,6)]+[slice(6+j.dof_idx,9+j.dof_idx) for j in g.joints if j.get_dof_dim()==3]:
        rot=R.from_rotvec(ref[:,sl]).as_matrix(); mean=R.from_matrix(rot).mean().as_matrix()
        v=R.from_matrix(rot@mean.T).as_rotvec(); smooth=gaussian_filter1d(v[:-1],5,axis=0,mode='wrap')
        guide[:,sl]=R.from_matrix(R.from_rotvec(np.r_[smooth,smooth[:1]]).as_matrix()@mean).as_rotvec()
    count=10; stride=count+3
    B=CubicSpline(np.linspace(0,1,count+1),np.r_[np.eye(count),np.eye(count)[:1]],bc_type='periodic')(np.linspace(0,1,n))
    displacement=old[-1,:3]-old[0,:3]; displacement[2]=0
    hands=[]
    for upper,lo,hi in [(3,12,36),(6,43,65)]:
        end=upper+2; gi=next(i for i,s in enumerate(g.gs) if s['body']==g.names[end])
        unwrapped=np.where(phase<lo,phase+54,phase) if hi>54 else phase
        u=np.clip((unwrapped-lo)/(hi-lo),0,1); swing=(unwrapped>lo)&(unwrapped<hi)
        envelope=np.where(swing,np.sin(np.pi*u)**2,0); ease=u**3*(10-15*u+6*u*u)
        shift=np.where((phase<lo)[:,None],-displacement[:2],0) if hi>54 else np.zeros((n,2))
        offset=ease[:,None]*displacement[:2]+shift
        old_centre=op[:,end]+np.einsum('nij,j->ni',orr[:,end],g.gp[gi])
        anchor=(old_centre[:,:2]-offset)[~swing].mean(0)
        rot=rr[:,end]; gr=rot@g.gr[gi]
        gp=np.einsum('nij,j->ni',rot,g.gp[gi])
        support=np.sqrt(gr[:,2]**2+.01**2)@g.gs[gi]['size']-gp[:,2]
        wrist_offset=np.c_[-gp[:,:2],support]
        # Ground support constrains a PLANTED palm. It must not inject rotation-
        # driven vertical/XY jerks into the airborne wrist trajectory.
        cs=CubicSpline(phase,wrist_offset)
        edge=[[cs(t%54),np.zeros(3),np.zeros(3)] for t in [lo,hi]]
        swing_curve=BPoly.from_derivatives([lo,hi],edge)(unwrapped)
        blend=np.clip(np.minimum(unwrapped-lo,hi-unwrapped)/3.,0,1)
        blend=blend**3*(10-15*blend+6*blend**2)
        wrist_offset[swing]=(1-blend[swing,None])*wrist_offset[swing]+blend[swing,None]*swing_curve[swing]
        hands.append(dict(upper=upper,end=end,gi=gi,rot=rot,envelope=envelope,offset=offset,anchor=anchor,wrist_offset=wrist_offset))
    cache={}; calls=0
    def calc(x):
        if 'x' in cache and np.array_equal(x,cache['x']):return cache
        f=base.copy(); cons=[]
        root=pr[:,0]@R.from_rotvec(local_axis*x[-2]).as_matrix()
        f[:,3:6]=R.from_matrix(root).as_rotvec();f[:,:3]=prelean[:,:3]+np.einsum('nij,j->ni',pr[:,0]-root,pivot)
        for body in [9,12]:
            j=g.k.get_joint(body);f[:,6+j.dof_idx:9+j.dof_idx]=R.from_matrix(g.lr[body].T@root.transpose(0,2,1)@orr[:,body]).as_rotvec()
        f[:,6:9]=prelean[:,6:9];initial_p,initial_r=fk(g,f)
        ax=unit(np.einsum('nij,j->ni',root,local_axis));v=np.einsum('nij,j->ni',initial_r[:,1],g.lp[2]);par=ax*np.sum(ax*v,axis=1)[:,None]
        ha=(v-par)[:,2];hb=np.cross(ax,v)[:,2];hc=par[:,2]
        height_delta=B@x[2*stride+count:-2]
        value=(x[-1]+height_delta-head_offset_z-initial_p[:,1,2]-hc)/np.hypot(ha,hb)
        phi=np.arctan2(hb,ha);delta=np.arccos(np.clip(value,-.999999,.999999))
        choices=(np.c_[phi+delta,phi-delta]+np.pi)%(2*np.pi)-np.pi
        theta=choices[np.arange(n),np.argmin(abs(choices),axis=1)]
        torso=R.from_rotvec(ax*theta[:,None]).as_matrix()@initial_r[:,1]
        twist=B@x[2*stride:2*stride+count]; tr=torso@R.from_rotvec(unit(g.lp[2])[None,:]*twist[:,None]).as_matrix()
        f[:,6:9]=R.from_matrix(g.lr[1].T@root.transpose(0,2,1)@tr).as_rotvec()
        f[:,9:12]=R.from_matrix(g.lr[2].T@tr.transpose(0,2,1)@rr[:,2]).as_rotvec()
        fp,fr=fk(g,f)
        cons.append(.99999-abs(value))
        tc=x[2*stride:2*stride+count];ddt=np.roll(tc,1)-2*tc+np.roll(tc,-1)
        hc_ctl=x[2*stride+count:-2];hdd=np.roll(hc_ctl,1)-2*hc_ctl+np.roll(hc_ctl,-1)
        cost=.05*np.mean(twist**2)+.2*np.mean(ddt**2)+1000*(x[-1]-reference_head_centre.mean())**2+.5*(x[-2]-lean)**2+5000*np.mean(height_delta**2)+500*np.mean(hdd**2)
        for i,h in enumerate(hands):
            v=x[i*stride:(i+1)*stride]; tip=np.zeros((n,3))
            tip[:,:2]=h['anchor']+v[:2]+h['offset']+h['wrist_offset'][:,:2]
            tip[:,2]=.0015+h['wrist_offset'][:,2]+h['envelope']*v[2]
            cons.append(np.linalg.norm(g.lp[h['upper']+1])+np.linalg.norm(g.lp[h['end']])-.015-np.linalg.norm(tip-fp[:,h['upper']],axis=1))
            f=arm(g,f,guide,tip,h['rot'],h['upper'],B@v[3:],allow_unreachable=True)
            dd=np.roll(v[3:],1)-2*v[3:]+np.roll(v[3:],-1)
            cost+=30*np.mean(v[:2]**2)+3*(v[2]-.13)**2+.01*np.mean(v[3:]**2)+.1*np.mean(dd**2)
        p,r=fk(g,f)
        for b in range(1,9):cons.append(joint_margins(g,f,b).ravel()+1e-6)
        for b in [9,12]:cons.append(joint_margins(g,f,b).ravel()-np.minimum(joint_margins(g,old,b).ravel(),0)+1e-6)
        for b in [4,7]:
            cost+=.0004*np.mean((np.diff(p[:,b],n=2,axis=0)/dt**2)**2)
        for gi,s in enumerate(g.gs):
            b=g.gb[gi]; gr=r[:,b]@g.gr[gi]; gp=p[:,b]+np.einsum('nij,j->ni',r[:,b],g.gp[gi])
            extent=np.abs(gr[:,2])@s['size'] if s['type']=='box' else s['size'][0]+abs(gr[:,2,2])*s['size'][1]
            cons.append(gp[:,2]-extent-.0005)
        cache.update(x=x.copy(),f=f,p=p,r=r,cost=cost,cons=np.concatenate(cons));return cache
    start=np.zeros(2*stride+2*count+2); bounds=[]
    for i in range(2):
        start[i*stride+2]=.13; bounds += [(-.25,.25)]*2+[(.04,.3)]+[(-3.,3.)]*count
    bounds += [(-.6,.6)]*count
    bounds += [(-.008,.008)]*count
    start[-2]=lean;bounds += [(0.05,.55)]
    start[-1]=old_head_centre.mean()+.03; bounds += [(float(old_head_centre.mean()),float(reference_head_centre.mean()))]
    probe=OUT/'reference-upper-probe.npz'
    if '--warm' in sys.argv and probe.exists():
        previous=np.load(probe)['parameters']
        if len(previous)==len(start):start[:]=previous
        elif len(previous)==2*stride+count+2:start[:2*stride+count]=previous[:-2];start[-2:]=previous[-2:]
        elif len(previous)==2*stride:start[:2*stride]=previous
    def progress(x):
        nonlocal calls
        calls+=1
        if calls%10==0:
            np.savez(probe,frames=calc(x)['f'],parameters=x)
            print(calls,'margin',calc(x)['cons'].min(),'index',calc(x)['cons'].argmin(),'cost',calc(x)['cost'],'head',x[-1],'lean',np.rad2deg(x[-2]),flush=True)
    start=np.clip(start,np.array(bounds)[:,0]+1e-10,np.array(bounds)[:,1]-1e-10)
    if '--stage-probe' in sys.argv:
        from types import SimpleNamespace
        res=SimpleNamespace(x=np.load(probe)['parameters'],success=True,message='Revalidate saved solve')
    else:
        feas=least_squares(lambda x:np.r_[np.minimum(calc(x)['cons'],0),.0003*(x-start)],start,bounds=np.array(bounds).T,max_nfev=150)
        np.savez(probe,frames=calc(feas.x)['f'],parameters=feas.x)
        print('feasible',calc(feas.x)['cons'].min(),'index',calc(feas.x)['cons'].argmin(),flush=True)
        res=minimize(lambda x:calc(x)['cost'],feas.x,method='SLSQP',bounds=bounds,constraints=[dict(type='ineq',fun=lambda x:calc(x)['cons'])],callback=progress,options=dict(maxiter=100,ftol=1e-7,eps=1e-6))
    cc=calc(res.x);np.savez(probe,frames=cc['f'],parameters=res.x)
    print(res.success,res.message,'margin',cc['cons'].min(),flush=True)
    assert cc['cons'].min()>-2e-6
    f=cc['f'];dense=interpolate(g,f,16);rd=interpolate(g,ref,16);p,r,bottom=sample(g,dense);pr,rrd=fk(g,rd);po,ro=fk(g,interpolate(g,old,16))
    head_z=p[:,2,2]+np.einsum('nij,j->ni',r[:,2],g.gp[head_gi])[:,2]
    report=dict(head_height_error_cm=[float((p[:,2,2]-pr[:,2,2]).min()*100),float((p[:,2,2]-pr[:,2,2]).max()*100)],
        pelvis_lean_deg=float(np.rad2deg(res.x[-2])),head_centre_height_cm=float(res.x[-1]*100),head_centre_vertical_range_cm=float(np.ptp(head_z)*100),
        head_centre_before_vertical_range_cm=float(np.ptp(old_head_centre)*100),
        head_height_range_cm=float(np.ptp(p[:,2,2])*100),reference_head_height_range_cm=float(np.ptp(pr[:,2,2])*100),
        rotation_error_deg={g.names[b]:float(np.rad2deg(R.from_matrix(r[:,b]@rrd[:,b].transpose(0,2,1)).magnitude()).max()) for b in [2,5,8]},
        floor_min_cm=float(bottom.min()*100),geometry=g.audit(interpolate(g,f,4)),
        leg_origin_error_cm=float(np.linalg.norm(p[:,9:]-po[:,9:],axis=-1).max()*100),
        joint_margins={g.names[b]:float(joint_margins(g,dense,b).min()) for b in range(1,9)},
        before=metrics(g,old,m['fps']),after=metrics(g,f,m['fps']),reference=metrics(g,ref,m['fps']))
    phase_dense=np.linspace(0,54,len(dense));contacts={}
    for upper in [3,6]:
        end=upper+2;gi=next(i for i,s in enumerate(g.gs) if s['body']==g.names[end])
        centre=p[:,end]+np.einsum('nij,j->ni',r[:,end],g.gp[gi])
        stance=((phase_dense<=12)|(phase_dense>=36)) if upper==3 else ((phase_dense>=11)&(phase_dense<=43))
        if upper==3:centre[phase_dense>=36]-=displacement
        bend=np.rad2deg(np.arccos(np.clip(np.sum(unit(p[:,upper+1]-p[:,upper])*unit(p[:,end]-p[:,upper+1]),axis=1),-1,1)))
        contacts[g.names[end]]=dict(stance_centre_xy_range_mm=(np.ptp(centre[stance,:2],axis=0)*1000).tolist(),minimum_elbow_bend_deg=float(bend.min()))
    report['contact_quality']=contacts
    (OUT/'reference-upper.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['before','after','reference']},indent=2),flush=True)
    assert report['head_centre_vertical_range_cm']<2.
    assert max(report['rotation_error_deg'].values())<.1
    assert bottom.min()>.0004 and report['geometry']['arm_leg_worst_penetration_cm']<.1
    assert report['leg_origin_error_cm']<.001 and min(report['joint_margins'].values())>-2e-5
    assert max(max(q['stance_centre_xy_range_mm']) for q in contacts.values())<.3
    assert min(q['minimum_elbow_bend_deg'] for q in contacts.values())>20
    m['frames']=f;path.write_bytes(pickle.dumps(m));meta=json.loads(path.with_suffix('.json').read_text())
    meta.update(reference_upper=report,candidate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),description='Original hand rotation restored; torso compensation stabilizes visible head height. Pelvis lean and compensated legs retained; arms refitted to contacts.')
    path.with_suffix('.json').write_text(json.dumps(meta,indent=2))


if __name__=='__main__':main()
