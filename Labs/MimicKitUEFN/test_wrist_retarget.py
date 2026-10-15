"""Check restored wrist motion against original cuts and preserve other DOFs."""
import json,pickle,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit'))
from anim.mjcf_char_model import MJCFCharModel

old=ROOT/'Saved/MimicKitUEFN/before-wrists'
a=MJCFCharModel('cpu');a.load(str(old/'humanoid_uefn.xml'))
b=MJCFCharModel('cpu');b.load(str(HERE/'humanoid_uefn.xml'))
data=json.loads((HERE/'omni-preview.json').read_text())
assert a.get_body_names()==b.get_body_names()
worst=0.;rows=[]
for clip in data['clips']:
    before=pickle.load((old/'omni'/(clip['id']+'.pkl')).open('rb'))['frames']
    after=pickle.load((ROOT/'Saved/MimicKitUEFN/omni'/(clip['id']+'.pkl')).open('rb'))['frames']
    np.testing.assert_array_equal(before[:,:6],after[:,:6])
    for i,name in enumerate(b.get_body_names()[1:],1):
        ja,jb=a.get_joint(i),b.get_joint(i)
        if name in ('left_hand','right_hand'):continue
        width=ja.get_dof_dim()
        np.testing.assert_array_equal(before[:,6+ja.dof_idx:6+ja.dof_idx+width],after[:,6+jb.dof_idx:6+jb.dof_idx+width])
    errors={}
    for side in ('left','right'):
        source=np.array(clip['source'])[:,data['source_names'].index('hand_'+side[0]),3:]
        actual=np.array(clip['reduced'])[:,data['names'].index(side+'_hand'),3:]
        error=float(np.degrees((R.from_quat(source).inv()*R.from_quat(actual)).magnitude()).max())
        assert error<.0001,(clip['id'],side,error)
        worst=max(worst,error);errors[side]=error
    rows.append(dict(clip=clip['id'],hand_orientation_max_degrees=errors))
report=dict(passed=True,clips=len(rows),hand_orientation_max_degrees=worst,
            root_and_nonwrist_joint_channels_bit_identical=True,rows=rows)
(ROOT/'Saved/MimicKitUEFN/wrist-retarget-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
