"""Select a planted standing frame, preserving the source articulation."""
import json,pickle,sys
from pathlib import Path
import numpy as np
import torch
from scipy.spatial.transform import Rotation
from scipy.spatial import ConvexHull

ROOT=Path(__file__).resolve().parents[2]
REPO=ROOT/'Saved/MimicKit/vendor/MimicKit'
sys.path.insert(0,str(REPO/'mimickit'))
from anim.mjcf_char_model import MJCFCharModel
from util import torch_util
from replay import geometry

def main():
    model=MJCFCharModel('cpu');model.load(str(REPO/'data/assets/humanoid/humanoid.xml'))
    geom=json.loads((ROOT/'Saved/MimicKit/geometry.json').read_text())
    candidates=[]
    for source in (ROOT/'Saved/MimicKit/amp-standing').glob('humanoid_getup*.pkl'):
        data=pickle.loads(source.read_bytes())
        frames=np.asarray(data['frames'],dtype=np.float32)
        for index in range(max(0,len(frames)-60),len(frames)):
            frame=frames[index].copy();frame[:2]=0
            q=Rotation.from_rotvec(frame[3:6]);heading=np.arctan2(q.as_matrix()[1,0],q.as_matrix()[0,0])
            frame[3:6]=(Rotation.from_rotvec([0,0,-heading])*q).as_rotvec()
            v=torch.tensor(frame)[None]
            p,r=model.forward_kinematics(v[:,:3],torch_util.exp_map_to_quat(v[:,3:6]),model.dof_to_rot(v[:,6:]))
            p=p[0].numpy();r=Rotation.from_quat(r[0].numpy()).as_matrix()
            bottoms=[];corners=[]
            for shape in geom['shapes']:
                if 'foot' not in shape['bone']:continue
                i=geom['names'].index(shape['bone'])
                axes=r[i]@np.array(shape['axes']).T
                center=p[i]+r[i]@shape['position']
                signs=np.array([[x,y,z] for x in [-1,1] for y in [-1,1] for z in [-1,1]])
                points=center+(signs*np.array(shape['dimensions'])/2)@axes.T
                bottoms.append(float(points[:,2].min()));corners.extend(points[:,:2])
            if p[0,2]<.84 or abs(bottoms[0]-bottoms[1])>.03:continue
            hull=ConvexHull(corners)
            # Pelvis support margin is a selection check, not a stability claim.
            margin=-max(hull.equations[:,:2]@p[0,:2]+hull.equations[:,2])
            if margin<.025:continue
            speed=np.linalg.norm(frames[index,6:]-frames[max(0,index-1),6:])*data['fps']
            score=abs(bottoms[0]-bottoms[1])+speed*.1
            frame[2]+=.002-min(bottoms)
            candidates.append((score,frame,source.name,index,bottoms,margin,speed))
    assert candidates,'No planted standing frame found'
    score,frame,source,index,bottoms,margin,speed=min(candidates,key=lambda c:c[0])
    target=Path(__file__).with_name('amp_standing_target.pkl')
    target.write_bytes(pickle.dumps(dict(loop_mode=1,fps=30,frames=np.tile(frame,(61,1)).tolist())))
    report=dict(source=source,source_frame=index,reference_frames=61,fps=30,pose=frame.tolist(),
        original_foot_bottoms_m=bottoms,foot_height_difference_m=abs(bottoms[0]-bottoms[1]),
        pelvis_support_margin_m=float(margin),source_joint_speed_norm=float(speed),
        changes='Only root XY/heading normalization and vertical floor placement; all joint angles preserved')
    target.with_suffix('.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))

if __name__=='__main__':main()
