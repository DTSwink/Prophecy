"""Check locked-twist clamp and actual bilateral rows against Jolt's construction."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Saved/MimicKitCrawl/package/assets/MimicKitTransfer'))
import numpy as np
from scipy.spatial.transform import Rotation as R
import warp as wp
from jolt_limit_directions import append
from limit_projection_gpu import clamp_rotation
from sequential_contact_gpu import ContactProblem

@wp.kernel(enable_backward=False)
def project(rot:wp.array(dtype=wp.quat),out:wp.array(dtype=wp.quat)):
    i=wp.tid();out[i]=clamp_rotation(rot[i],wp.vec3(0.,1.,1.))

def main():
    rng=np.random.default_rng(3521);n=129
    swing=R.from_rotvec(np.c_[np.zeros(n),rng.uniform(-.25,.25,(n,2))])
    twist=R.from_rotvec(np.c_[rng.uniform(-1.,1.,n),np.zeros((n,2))])
    rotations=(swing*twist).as_quat();rotations[0]=[0,0,0,1]
    expected=swing.as_quat();expected[0]=[0,0,0,1]
    wp.init();device='cuda:0';wp.set_device(device)
    output=wp.zeros(n,dtype=wp.quat,device=device)
    wp.launch(project,dim=n,inputs=[wp.array(rotations,dtype=wp.quat,device=device),output],device=device)
    error=(R.from_quat(expected).inv()*R.from_quat(output.numpy())).magnitude()
    assert error.max()<2e-6
    p=ContactProblem();p.nv=3
    p.nlimit=wp.zeros(n,dtype=int,device=device);p.limit_J=wp.zeros((n,3,3),device=device)
    p.limit_target=wp.zeros((n,3),device=device);p.limit_compliance=wp.zeros((n,3),device=device)
    p.limit_bilateral=wp.zeros((n,3),dtype=int,device=device)
    mapping=wp.zeros((n,3),dtype=int,device=device);errors=wp.zeros(n,dtype=int,device=device)
    args=[p,wp.array(rotations[:,[3,0,1,2]],dtype=float,device=device),wp.array([0],dtype=int,device=device),
        wp.array([[1,0,0,0]],dtype=wp.quat,device=device),wp.array([[.9,1.,1.]],dtype=wp.vec3,device=device),
        wp.array([[2,1,1]],dtype=wp.vec3i,device=device),wp.array([0],dtype=int,device=device),
        wp.array([0],dtype=int,device=device),mapping,errors]
    wp.launch(append,dim=n,inputs=args,device=device)
    np.testing.assert_array_equal(p.nlimit.numpy(),1)
    np.testing.assert_array_equal(p.limit_bilateral.numpy()[:,0],1)
    np.testing.assert_array_equal(p.limit_J.numpy()[:,0],np.tile([1,0,0],(n,1)))
    assert not errors.numpy().any()
    # Jolt's world axis (constraintFrame*swing).X becomes child-local X.
    axis=(swing*twist).inv().apply(swing.apply(np.tile([1.,0.,0.],(n,1))))
    np.testing.assert_allclose(axis,[np.array([1.,0.,0.])]*n,atol=1e-12)
    report=dict(passed=True,cases=n,max_clamp_error_rad=float(error.max()),
        locked_rows_always_active=True,bilateral=True,zero_twist_tested=True,
        source='Jolt SwingTwistConstraintPart.h:420-424; clamp uses identity twist')
    (ROOT/'Saved/MimicKitCrawl/locked-twist-test.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':main()
