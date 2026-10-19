"""Named cap mapping and preservation checks without starting a simulator."""
import numpy as np
from torque_envelope import apply_torque_envelope


class Array:
    def __init__(self,values):self.values=np.array(values,dtype=np.float32)
    def numpy(self):return self.values.copy()
    def assign(self,values):self.values[:]=values


def main():
    class Model:pass
    model=Model();model.body_label=['a/pelvis','a/arm','a/elbow','b/pelvis','b/arm','b/elbow']
    model.joint_qd_start=Array([0,6,9,10,16,19,20])
    model.joint_effort_limit=Array(([0]*6+[100]*3+[70])*2)
    before=model.joint_effort_limit.numpy()
    report=apply_torque_envelope(model,{'arm:1':125,'elbow':65})
    expected=before.copy();expected[[7,17]]=125
    np.testing.assert_array_equal(model.joint_effort_limit.numpy(),expected)
    assert report['axes']['elbow']['applied_nm']==70
    for request in ({'missing':123},{'arm:0':float('nan')},{'arm:0':-1}):
        try:apply_torque_envelope(model,request)
        except ValueError:pass
        else:raise AssertionError('Accepted invalid envelope')
    np.testing.assert_array_equal(model.joint_effort_limit.numpy(),expected)
    print('PASS: named axes, all worlds, no reductions, invalid values rejected')


if __name__=='__main__':main()
