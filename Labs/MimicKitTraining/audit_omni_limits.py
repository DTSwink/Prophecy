"""Read-only reference admissibility audit before paying for training."""
import sys,json,pickle
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(ROOT/'Labs/MimicKitUEFN'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
import numpy as np
from scipy.spatial.transform import Rotation as R
from test_model import coords,violation
from anim.mjcf_char_model import MJCFCharModel

def main():
    m=MJCFCharModel('cpu');m.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    meta=json.loads((ROOT/'Labs/MimicKitUEFN/limits.json').read_text())
    f=pickle.loads((ROOT/'Saved/MimicKitUEFN/omni/M_Neutral_Run_Loop_LR.pkl').read_bytes())['frames'];out=[]
    for j in meta['joints']:
        k=m.get_joint(m.get_body_names().index(j['body']));width=3 if j['kind']=='ball' else 1
        a=f[:,6+k.dof_idx:6+k.dof_idx+width]
        if j['kind']=='ball':
            q=(R.from_quat(np.array(j['reference_wxyz'])[[1,2,3,0]])*R.from_rotvec(a)).as_quat()[:,[3,0,1,2]]
            v=coords(q);bad=violation(v,j)
            angles=np.rad2deg(np.column_stack((v[:,0],2*np.arcsin(np.clip(v[:,1:],-1,1)))))
            out.append(dict(body=j['body'],outside_frames=int(bad.sum()),frames=len(f),peak_abs_angles_deg=abs(angles).max(0).tolist(),limit_deg=np.rad2deg(j['limits_rad']).tolist(),modes=j['modes']))
        else:
            low,high=j['range_rad'];bad=(a[:,0]<low)|(a[:,0]>high)
            out.append(dict(body=j['body'],outside_frames=int(bad.sum()),frames=len(f),minmax_deg=np.rad2deg([a.min(),a.max()]).tolist(),bounds_deg=np.rad2deg([low,high]).tolist()))
    (ROOT/'Saved/MimicKitUEFN/runLR-limit-audit.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
