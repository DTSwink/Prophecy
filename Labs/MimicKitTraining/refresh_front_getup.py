"""Rebuild only edited front get-up with the currently deployed preparation."""
import hashlib,json,pickle,sys,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'
STAGE=OUT/'front-foot-update-20261019'
BASE=OUT/'velocity-mse-x2-source.zip'

def main():
    import prepare_recovery_starts as prep
    prep.OUT=STAGE;prep.NAMES=('getUp_front_quick',)
    prep.convert()
    prep.prepare()
    # Existing helpers process both banks. Reconstruct the unchanged back as
    # a control, but only promote the front files into the training package.
    data=json.loads((STAGE/'data.json').read_text())
    previous=json.loads((OUT/'recovery-update-20261018/data.json').read_text())
    data['clips'].append(next(c for c in previous['clips'] if c['id']=='getUp_back_quick'))
    (STAGE/'data.json').write_text(json.dumps(data,separators=(',',':')))
    with zipfile.ZipFile(BASE) as z:
        (STAGE/'getUp_back_quick_robotic.pkl').write_bytes(z.read('motions/recovery/getUp_back_quick_robotic.pkl'))
    import prepare_recovery_hand_ik as hands
    import prepare_recovery_foot_resets as feet
    hands.main(STAGE);feet.main(STAGE)
    import numpy as np
    from scipy.spatial.transform import Rotation as R
    model=hands.ae.rt.MJCFCharModel('cpu');model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    with zipfile.ZipFile(BASE) as z:
        for suffix in ('robotic','reset_hand_ik','reset_floor_ik'):
            back='getUp_back_quick_'+suffix+'.pkl'
            old=pickle.loads(z.read('motions/recovery/'+back))['frames']
            new=pickle.loads((STAGE/back).read_bytes())['frames']
            np.testing.assert_array_equal(new,old)
        old=pickle.loads(z.read('motions/recovery/getUp_front_quick_robotic.pkl'))
        new=pickle.loads((STAGE/'getUp_front_quick_robotic.pkl').read_bytes())
    a,b=old['frames'],new['frames']
    assert a.shape==b.shape and new['fps']==old['fps']==30 and new['loop_mode']==0
    assert np.isfinite(b).all()
    pp,pq=hands.ae.fk(model,a);np_,nq=hands.ae.fk(model,b)
    names=model.get_body_names();foot=names.index('right_foot')
    angle=(R.from_quat(pq[:,foot]).inv()*R.from_quat(nq[:,foot])).magnitude()*180/np.pi
    report=dict(frames=len(b),fps=new['fps'],source=json.loads((STAGE/'imports.json').read_text())[0],
        root_max_coordinate_change=float(np.max(abs(a[:,:6]-b[:,:6]))),
        first_frame_max_coordinate_change=float(np.max(abs(a[0]-b[0]))),
        right_foot_angle_change_degrees=angle.tolist(),
        right_foot_final_angle_change_degrees=float(angle[-1]),
        body_max_position_change_m={n:float(np.max(np.linalg.norm(pp[:,i]-np_[:,i],axis=-1))) for i,n in enumerate(names)},
        back_reset_frames_unchanged=True,
        method='Same deployed anchor projection/conditional foot lift and fixed-pole reset-only hand/foot IK; no pelvis shifts or abandoned arc cleanup')
    (STAGE/'verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('source','right_foot_angle_change_degrees')}),flush=True)

if __name__=='__main__':main()
