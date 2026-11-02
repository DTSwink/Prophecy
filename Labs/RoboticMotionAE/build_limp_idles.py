"""Offline limp idle drafts. No live training/package writes or GPU use."""
import hashlib, itertools, json, pickle
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from scipy.optimize import minimize, least_squares
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry, ROOT, P
from clean_slow_contacts import margins, solve_leg

OUT = ROOT/'Saved/MimicKitSlowLoco/limp-idles-preview-20261101'
IDLE = ROOT/'Saved/MimicKitLocomotion/final-phase-source/motions/M_Neutral_Stand_Idle_Loop_Unarmed.pkl'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    g = Geometry()
    xml = ET.parse(P/'assets/uefn/humanoid_uefn.xml')
    by_name = {b.attrib['name']: b for b in xml.findall('.//body')}
    masses = np.array([float(by_name[n].find('inertial').attrib['mass']) for n in g.names])
    offsets = np.array([np.fromstring(by_name[n].find('inertial').attrib['pos'], sep=' ') for n in g.names])

    def com(p, r):
        return ((p+np.einsum('bij,bj->bi',r,offsets))*masses[:,None]).sum(0)/masses.sum()

    idle = pickle.loads(IDLE.read_bytes())
    idle_frames = idle['frames'][:-1].astype(float)
    n = len(idle_frames)
    # Keep the normal idle's full slow pelvis/upper-body motion (up to0.6Hz),
    # including its0.3Hz breathing, over the original ten-second loop.
    chest = R.from_rotvec(idle_frames[:,6:9])
    chest_delta = (chest.mean().inv()*chest).as_rotvec()
    spectrum = np.fft.rfft(chest_delta,axis=0)
    freqs = np.fft.rfftfreq(n,1/idle['fps'])
    allowed = np.where((freqs>=.18)&(freqs<=.45))[0]
    harmonic = int(allowed[np.argmax(np.sum(abs(spectrum[allowed])**2,axis=1))])
    frequency = float(freqs[harmonic]); duration = n/idle['fps']
    fps = 120.; times = np.linspace(0,duration,round(duration*fps)+1)
    def periodic(delta):
        coefs=np.fft.rfft(delta,axis=0)/n
        return sum(2*np.real(np.exp(2j*np.pi*freqs[k]*times[:,None])*coefs[k])
                   for k in range(1,len(freqs)) if freqs[k]<=.60001)
    idle_root=R.from_rotvec(idle_frames[:,3:6])
    pelvis_rotation=periodic((idle_root.mean().inv()*idle_root).as_rotvec())
    pelvis_height=periodic(idle_frames[:,2:3]-idle_frames[:,2:3].mean(0))[:,0]
    breathing = {}
    arm_mean={}
    for body in range(1,9):
        joint = g.k.get_joint(body); start=6+joint.dof_idx; dim=joint.get_dof_dim()
        source = idle_frames[:,start:start+dim]
        if dim==3:
            rotations=R.from_rotvec(source)
            delta=(rotations.mean().inv()*rotations).as_rotvec()
        else: delta=source-source.mean(0)
        values=periodic(delta)
        breathing[body]=(start,dim,values)
        if body>=3:arm_mean[body]=rotations.mean().as_rotvec() if dim==3 else source.mean(0)

    clips=[];reports={}
    for name,active,passive in [('limpL',11,14),('limpR',14,11)]:
        source_path=P/'motions'/f'{name}.pkl'
        motion=pickle.loads(source_path.read_bytes());source=motion['frames'].astype(float)
        active_geom=int(np.flatnonzero(g.gb==active)[0])
        ps=[];rs=[];centres=[];floors=[]
        for frame in source:
            p,r=g.fk(frame);g.set_pose(p,r)
            ps.append(p);rs.append(r);centres.append(g.d.geom_xpos[active_geom].copy());floors.append(g.floors()[active_geom])
        centres=np.array(centres);speed=np.linalg.norm(np.gradient(centres,axis=0)*motion['fps'],axis=1)
        scores=[]
        for i,(p,r) in enumerate(zip(ps,rs)):
            offset=np.linalg.norm((com(p,r)-centres[i])[:2])
            grounded=floors[i]<.005 and speed[i]<.03
            scores.append(dict(frame=i,grounded=bool(grounded),active_foot_speed_m_s=float(speed[i]),
                com_horizontal_distance_m=float(offset),score=float(offset+.1*speed[i]) if grounded else 999.))
        selected=min(scores,key=lambda x:x['score']); frame=source[selected['frame']].copy()
        # Flatten just the supporting ankle (<~1degree); keep the authored legs,
        # pelvis and upper body. Root height puts the entire sole1.5mm above floor.
        p,r=g.fk(frame);g.set_pose(p,r)
        shape_r=g.d.geom_xmat[active_geom].reshape(3,3).copy()
        normal=np.array([0.,0.,np.sign(shape_r[2,0])])
        length=shape_r[:,1].copy();length[2]=0;length/=np.linalg.norm(length)
        desired=np.column_stack((normal,length,np.cross(normal,length)))@g.gr[active_geom].T
        joint=g.k.get_joint(active);sl=slice(6+joint.dof_idx,9+joint.dof_idx)
        frame[sl]=R.from_matrix(g.lr[active].T@r[g.parents[active]].T@desired).as_rotvec()
        p,r=g.fk(frame);g.set_pose(p,r)
        frame[:2]-=g.d.geom_xpos[active_geom,:2]
        frame[2]+=.0015-g.floors()[active_geom]
        # The source passive ankle slightly exceeds its real limit. Correct only
        # that ankle, keeping the dragging foot clear without asking it for support.
        j=g.k.get_joint(passive);ids=np.arange(6+j.dof_idx,9+j.dof_idx);x0=frame[ids].copy()
        def candidate(x):
            f=frame.copy();f[ids]=x;return f
        def constraints(x):
            f=candidate(x);p,r=g.fk(f);g.set_pose(p,r)
            return np.r_[margins(g,f,[passive])-1e-5,g.floors()[g.gb==passive]-.001]
        result=minimize(lambda x:np.sum((R.from_rotvec(x0).inv()*R.from_rotvec(x)).as_rotvec()**2),
            x0,method='SLSQP',constraints=[dict(type='ineq',fun=constraints)],options=dict(maxiter=150,ftol=1e-12))
        assert constraints(result.x).min()>-1e-6,result.message
        frame=candidate(result.x)
        passive_fix=float(np.rad2deg((R.from_rotvec(x0).inv()*R.from_rotvec(result.x)).magnitude()))
        for body,value in arm_mean.items():
            start,dim,_=breathing[body];frame[start:start+dim]=value
        original_root=frame[:3].copy()
        # Exact analytic two-bone IK: keep BOTH world-space foot transforms fixed
        # while the pelvis translates/rotates. Knee branch follows the source pose.
        anchor_pos,anchor_rot=g.fk(frame)
        def pinned(f):
            f=f.copy();p,r=g.fk(f)
            for upper in (9,12):
                mid,end=upper+1,upper+2
                hj,mj,ej=[g.k.get_joint(b) for b in (upper,mid,end)]
                ur,angle,mr,_=solve_leg(p[upper],p[mid],p[end],anchor_pos[end],
                    g.lp[mid],g.lp[end],g.lr[mid],mj.axis.numpy(),f[6+mj.dof_idx])
                f[6+hj.dof_idx:9+hj.dof_idx]=R.from_matrix(g.lr[upper].T@r[g.parents[upper]].T@ur).as_rotvec()
                f[6+mj.dof_idx]=angle
                f[6+ej.dof_idx:9+ej.dof_idx]=R.from_matrix(g.lr[end].T@mr.T@anchor_rot[end]).as_rotvec()
            return f
        def balance(f,guess=None):
            def residual(x):
                trial=f.copy();trial[:2]=x;trial=pinned(trial)
                p,r=g.fk(trial);return com(p,r)[:2] # support centre is world XY zero
            x=f[:2] if guess is None else guess
            solution=least_squares(residual,x,xtol=1e-11,ftol=1e-11,gtol=1e-11,max_nfev=30)
            out=f.copy();out[:2]=solution.x;out=pinned(out)
            assert np.linalg.norm(residual(solution.x))<1e-6
            return out
        # Small downward adjustment only if the planted trailing leg needs reach.
        for lower_by in (0.,.005,.01,.015,.02,.03):
            base=frame.copy();base[2]-=lower_by
            try:
                balanced=balance(base)
                break
            except ValueError:continue
        else:raise RuntimeError('No reachable centred base pose')
        frame=balanced
        frames=np.tile(frame,(len(times),1))
        for body,(start,dim,delta) in breathing.items():
            if dim==3:frames[:,start:start+3]=(R.from_rotvec(frame[start:start+3])*R.from_rotvec(delta)).as_rotvec()
            else:frames[:,start]+=delta[:,0]
        frames[:,3:6]=(R.from_rotvec(frame[3:6])*R.from_rotvec(pelvis_rotation)).as_rotvec()
        frames[:,2]+=pelvis_height
        guess=frame[:2].copy()
        for i in range(len(frames)):
            frames[i]=balance(frames[i],guess);guess=frames[i,:2]
        frames[-1]=frames[0]
        name_idle=name+'_idle';dest=OUT/(name_idle+'.pkl')
        variants={};audit_rows=[]
        for variant,sequence in [('still',[frame]),('breathing',frames)]:
            rows=[]
            for f in sequence:
                p,r=g.fk(f);g.set_pose(p,r);bottom=g.floors();cm=com(p,r)
                cr=g.d.geom_xmat[active_geom].reshape(3,3)
                centre=g.d.geom_xpos[active_geom]
                local=cr.T@(np.r_[cm[:2],centre[2]]-centre)
                margin=min(g.gs[active_geom]['size'][1]-abs(local[1]),g.gs[active_geom]['size'][2]-abs(local[2]))
                corners=np.array(list(itertools.product((-1,1),repeat=3)))*g.gs[active_geom]['size']
                corners=centre+corners@cr.T;sole=corners[np.argsort(corners[:,2])[:4]]
                sole=sole[np.argsort(np.arctan2(sole[:,1]-centre[1],sole[:,0]-centre[0]))]
                rows.append(dict(p=np.round(g.d.geom_xpos,7).tolist(),q=np.round(R.from_matrix(g.d.geom_xmat.reshape(-1,3,3)).as_quat(),8).tolist(),
                    com=cm.tolist(),margin=float(margin),support=sole.tolist(),bottom=bottom.tolist()))
                if variant=='breathing':audit_rows.append((float(bottom.min()),float(margin)))
            variants[variant]=dict(fps=fps,rows=rows)
        audit=np.array(audit_rows);collision=g.audit(frames[::4])
        assert audit[:,0].min()>-.00001
        assert audit[:,1].min()>.015
        assert not collision['limit_violations'],collision['limit_violations']
        assert collision['worst_penetration_cm']<.01
        # Validate real FK foot pinning, rather than assuming frozen joint values.
        all_pos=[];all_rot=[];com_errors=[]
        for f in frames:
            p,r=g.fk(f);all_pos.append(p[[11,14]]);all_rot.append(r[[11,14]]);com_errors.append(np.linalg.norm(com(p,r)[:2]))
        all_pos=np.array(all_pos);all_rot=np.array(all_rot)
        pin_error=float(np.linalg.norm(all_pos-anchor_pos[[11,14]],axis=-1).max())
        pin_rotation_error=float(np.max(abs(all_rot-anchor_rot[[11,14]])))
        assert pin_error<1e-7 and pin_rotation_error<1e-7
        angular_jump=[]
        for b in range(1,9):
            j=g.k.get_joint(b);s=6+j.dof_idx;d=j.get_dof_dim()
            if d==3:
                q=R.from_rotvec(frames[:,s:s+3]);angular_jump.append(float(np.rad2deg((q[:-1].inv()*q[1:]).magnitude()).max()))
        dest.write_bytes(pickle.dumps(dict(frames=frames,fps=fps,loop_mode=motion['loop_mode'])))
        report=dict(name=name_idle,source_motion=name,source_frame=selected['frame'],selection=selected,
            active_foot=g.names[active],disabled_leg='left' if name=='limpL' else 'right',
            source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),draft_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
            breathing_source=str(IDLE),breathing_source_sha256=hashlib.sha256(IDLE.read_bytes()).hexdigest(),
            breathing_hz=frequency,loop_seconds=duration,fps=fps,frames=len(frames),
            minimum_support_margin_cm=float(audit[:,1].min()*100),minimum_floor_clearance_cm=float(audit[:,0].min()*100),
            passive_ankle_limit_correction_degrees=passive_fix,root_and_legs_static=False,
            base_pelvis_shift_cm=((frame[:3]-original_root)*100).tolist(),
            pelvis_translation_range_cm=(np.ptp(frames[:,:3],axis=0)*100).tolist(),
            pelvis_rotation_range_deg=(np.rad2deg(np.ptp(pelvis_rotation,axis=0))).tolist(),
            arms='normal unarmed idle mean and full slow movement',
            max_com_centre_error_mm=float(max(com_errors)*1000),foot_pinning_error_m=pin_error,
            foot_rotation_matrix_error=pin_rotation_error,
            max_upper_joint_step_degrees=max(angular_jump),loop_position_error=float(abs(frames[-1]-frames[0]).max()),
            geometry_audit=collision,selection_candidates=scores,
            validation_scope='Kinematic contact, mass-centre projection, limits and collision checks; not a learned policy or dynamic balance test')
        reports[name_idle]=report;clips.append(dict(name=name_idle,active_foot=g.names[active],variants=variants,report=report))
        print(name_idle,json.dumps({k:report[k] for k in ['source_frame','minimum_support_margin_cm','minimum_floor_clearance_cm','passive_ankle_limit_correction_degrees','max_upper_joint_step_degrees']}),flush=True)
    (OUT/'data.json').write_text(json.dumps(dict(geometry=g.gs,clips=clips,duration=duration),separators=(',',':')))
    (OUT/'report.json').write_text(json.dumps(reports,indent=2))
    for name in ('index.html','view.js'):
        (OUT/name).write_text((ROOT/'Labs/RoboticMotionAE/limp_idle_viewer'/name).read_text(encoding='utf-8'),encoding='utf-8')


if __name__=='__main__':main()
