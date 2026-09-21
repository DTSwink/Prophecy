"""Hinge coherence plus actual captured calf orientation continuity. Read-only."""
import argparse,pathlib,json,runpy,numpy as np
from scipy.spatial.transform import Rotation
folder=pathlib.Path(__file__).parent
H=runpy.run_path(str(folder/'CompareRecoveryLegs.py'))
off=H['OFF'];walk=H['WALK'];rot=H['rot'];unit=H['unit']
def inspect(name):
    path,pipe,metrics=H['load'](name);rows=[]
    for tick,r in pipe.items():
        if r.get('attack'):continue
        s=np.array(r['published_lower']);m=metrics[tick];prev=metrics.get(tick-1)
        row={'tick':tick,'tempering':r.get('tempering'),'legs':{}}
        for i,side in enumerate(('left','right')):
            o=9+16*i;h=17+4*i;k=off[h+1];kc=off[h+2];p,pc=np.array(walk['ik_local_pole_axes'][i]);thigh=rot(s[o+9:o+15]);upper=k@thigh
            hip=s[:3]+off[h]@rot(s[3:9]);lower=s[o:o+3]-hip-upper
            geom=unit(np.cross(upper,lower));encoded=unit(np.cross(unit(k),p))@thigh
            bend=np.degrees(np.arccos(np.clip(np.dot(unit(upper),unit(lower)),-1,1)))
            letter='l' if i==0 else 'r';t=Rotation.from_quat(m['bones']['thigh_'+letter]['target']['q']);c=Rotation.from_quat(m['bones']['calf_'+letter]['target']['q']);j=t.inv()*c
            data={'knee_bend_deg':float(bend),'hinge_vs_geometric_plane_deg':float(np.degrees(np.arccos(np.clip(abs(np.dot(geom,encoded)),-1,1)))),
                'hinge_cross_calf_magnitude':float(np.linalg.norm(np.cross(encoded,unit(lower)))),'calf_length_error_cm':float((np.linalg.norm(lower)-np.linalg.norm(kc))*100)}
            if prev:
                pt=Rotation.from_quat(prev['bones']['thigh_'+letter]['target']['q']);pcalf=Rotation.from_quat(prev['bones']['calf_'+letter]['target']['q']);pj=pt.inv()*pcalf
                data.update(calf_world_step_deg=float(np.degrees((c*pcalf.inv()).magnitude())),relative_knee_joint_step_deg=float(np.degrees((j*pj.inv()).magnitude())))
            row['legs'][side]=data
        rows.append(row)
    summary=[]
    for cycle in range(max(0,(max(metrics)-199)//120+1)):
        start=149+cycle*120
        for phase,(a,b) in {'tempered':(start,start+28),'normal_return':(start+30,start+50)}.items():
            rs=[r for r in rows if a<=r['tick']<=b and (bool(r['tempering']) if phase=='tempered' else not bool(r['tempering']))]
            rec={'cycle':cycle+1,'phase':phase,'legs':{}}
            for side in ('left','right'):
                legs=[r['legs'][side] for r in rs]
                rec['legs'][side]={key:{'max':max(v[key] for v in legs),'mean':float(np.mean([v[key] for v in legs]))} for key in legs[0]} if legs else {}
            summary.append(rec)
    result={'capture':str(path),'note':'Hinge-plane alignment is computed in published training coordinates; angles invariant to shared world carrier. World calf/knee-joint steps use captured interpolated target quaternions. Near-straight geometry should be reviewed alongside bend angle.','summary':summary,'rows':rows}
    (path/'recovery_hinge_continuity.json').write_text(json.dumps(result,indent=2))
    print(path.name)
    for r in summary:
        if r['phase']=='tempered':print(json.dumps(r))
    return result
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('captures',nargs='+');args=ap.parse_args()
    for name in args.captures:inspect(name)
